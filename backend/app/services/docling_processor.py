"""Docling PDF conversion with lazy initialization."""

from pathlib import Path
import logging
import threading
import time

logger = logging.getLogger("vectorbrain.docling")


def _log_timing(label: str, start: float, extra: str = "") -> float:
    """Log elapsed time since start and return new timestamp."""
    elapsed = time.perf_counter() - start
    logger.info("timing: %s took %.3fs %s", label, elapsed, extra)
    return time.perf_counter()


class DoclingConversionError(Exception):
    """The PDF could not be converted to a structured document."""


class DoclingProcessor:
    """Converts PDF files into DoclingDocument objects."""

    def __init__(self) -> None:
        self._converter = None
        self._lock = threading.Lock()

    def _get_converter(self):
        if self._converter is None:
            with self._lock:
                if self._converter is None:
                    from docling.datamodel.base_models import InputFormat
                    from docling.datamodel.pipeline_options import (
                        PdfPipelineOptions,
                        LayoutObjectDetectionOptions,
                        HeadingHierarchyOptions,
                    )
                    from docling.document_converter import (
                        DocumentConverter,
                        PdfFormatOption,
                    )

                    logger.info(
                        "initializing optimized Docling DocumentConverter"
                    )

                    # Keep Docling for PDF processing, but disable
                    # expensive OCR, table-structure, and other heavy features
                    # for normal text PDFs.
                    pipeline_options = PdfPipelineOptions()
                    pipeline_options.do_ocr = False
                    pipeline_options.do_table_structure = False
                    pipeline_options.do_chart_extraction = False
                    pipeline_options.do_code_enrichment = False
                    pipeline_options.do_formula_enrichment = False
                    pipeline_options.do_picture_classification = False
                    pipeline_options.do_picture_description = False
                    pipeline_options.generate_page_images = False
                    pipeline_options.generate_picture_images = False
                    pipeline_options.generate_table_images = False
                    pipeline_options.enable_remote_services = False
                    # Reduce image scale for faster layout model inference (0.5 = 2x linear, 4x area reduction).
                    pipeline_options.images_scale = 0.5

                    # Enable heading hierarchy from PDF metadata (bookmarks, numbering, style)
                    # to reduce reliance on layout analysis for heading detection.
                    pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(
                        enabled=True,
                        use_bookmarks=True,
                        use_numbering=True,
                        use_style=True,
                        use_font_style=True,
                    )

                    # Try to use ONNX Runtime for faster CPU inference of layout model.
                    # Falls back to Transformers engine if onnxruntime not available.
                    try:
                        from docling.models.inference_engines.object_detection.onnxruntime_engine import (
                            OnnxRuntimeObjectDetectionEngineOptions,
                        )
                        from docling.models.inference_engines.object_detection.factory import (
                            ObjectDetectionEngineType,
                        )

                        pipeline_options.layout_options = LayoutObjectDetectionOptions(
                            engine_options=OnnxRuntimeObjectDetectionEngineOptions(
                                engine_type=ObjectDetectionEngineType.ONNXRUNTIME,
                                score_threshold=0.3,
                            ),
                            model_spec=pipeline_options.layout_options.model_spec,
                        )
                        logger.info("using ONNX Runtime for layout model inference")
                    except ImportError:
                        logger.info("onnxruntime not available, using Transformers engine for layout model")

                    self._converter = DocumentConverter(
                        format_options={
                            InputFormat.PDF: PdfFormatOption(
                                pipeline_options=pipeline_options
                            )
                        }
                    )

        return self._converter

    def warmup(self) -> None:
        """Pre-load models by running a dummy conversion.
        
        Call this during application startup to avoid first-request latency.
        Uses a minimal in-memory PDF to trigger model loading.
        """
        try:
            # Create a minimal 1-page PDF in memory for warmup
            import io
            from pypdf import PdfWriter
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)  # Letter size
            buf = io.BytesIO()
            writer.write(buf)
            pdf_bytes = buf.getvalue()
            
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name
            
            logger.info("warming up Docling converter...")
            t0 = time.perf_counter()
            self.convert(tmp_path)
            elapsed = time.perf_counter() - t0
            logger.info("Docling warmup completed in %.3fs", elapsed)
        except Exception as exc:
            logger.warning("Docling warmup failed (non-fatal): %s", exc)
        finally:
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass

    def convert(self, pdf_path: str | Path):
        """Convert a PDF file. Returns the DoclingDocument."""

        from docling.document_converter import ConversionStatus

        path = Path(pdf_path)

        logger.info("converting %s", path.name)
        t0 = time.perf_counter()

        converter = self._get_converter()
        t0 = _log_timing("docling_init", t0)

        result = converter.convert(str(path))
        t0 = _log_timing("docling_convert_internal", t0, f"status={result.status}")

        if result.status != ConversionStatus.SUCCESS:
            raise DoclingConversionError(
                f"Could not process {path.name}: conversion {result.status}."
            )

        doc = result.document

        if not doc.texts:
            raise DoclingConversionError(
                f"Could not process {path.name}: no extractable text found."
            )

        _log_timing("docling_convert_total", t0, f"pages={len(doc.pages)}")
        return doc

    @staticmethod
    def page_count(document) -> int:
        return len(document.pages)