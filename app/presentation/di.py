"""
Racine de composition (composition root).

C'est le seul endroit du projet où une couche externe (``pypdf``, ``Pillow``)
est reliée aux cas d'usage. L'interface ne reçoit que ce conteneur et
n'importe jamais ``PyPdfRepository`` ni ``pypdf`` directement — elle pourrait
fonctionner à l'identique avec n'importe quelle autre implémentation des
ports du domaine.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.batch import BatchProcessUseCase
from app.application.extract_cases import ExtractImagesUseCase, ExtractTextUseCase
from app.application.optimize_cases import (
    CompressPdfUseCase,
    ReadBookmarksUseCase,
    ReadMetadataUseCase,
    WriteBookmarksUseCase,
    WriteMetadataUseCase,
)
from app.application.organize_cases import (
    CropPagesUseCase,
    InsertPagesUseCase,
    InterleavePdfsUseCase,
    ReorderPagesUseCase,
)
from app.application.unmark_cases import RemoveWatermarksUseCase, ScanWatermarksUseCase
from app.application.stamp_cases import NumberPagesUseCase, StampImageUseCase, WatermarkTextUseCase
from app.application.use_cases import (
    CountPagesUseCase,
    DeletePagesUseCase,
    ExtractPagesUseCase,
    ImagesToPdfUseCase,
    LandscapePairUseCase,
    MergePdfsUseCase,
    ProtectPdfUseCase,
    RotatePagesUseCase,
    SplitPdfUseCase,
    UnlockPdfUseCase,
)
from app.domain.archive import ArchiveWriter
from app.domain.image_repository import ImageToPdfConverter
from app.domain.optimization import PdfOptimizer
from app.domain.options import StampKind
from app.domain.repositories import PdfRepository
from app.domain.stamping import PdfStamper
from app.domain.unmarking import WatermarkRemover
from app.infrastructure.pillow_image_repository import PillowImageRepository
from app.infrastructure.pypdf_optimizer import PyPdfOptimizer
from app.infrastructure.pypdf_repository import PyPdfRepository
from app.infrastructure.pypdf_stamper import PyPdfStamper
from app.infrastructure.pypdf_watermark_remover import PyPdfWatermarkRemover
from app.infrastructure.zip_archive import ZipArchiveWriter


@dataclass(frozen=True, slots=True)
class UseCases:
    # -- outils d'origine
    count_pages: CountPagesUseCase
    split_pdf: SplitPdfUseCase
    extract_pages: ExtractPagesUseCase
    merge_pdfs: MergePdfsUseCase
    delete_pages: DeletePagesUseCase
    rotate_pages: RotatePagesUseCase
    landscape_pair: LandscapePairUseCase
    protect_pdf: ProtectPdfUseCase
    unlock_pdf: UnlockPdfUseCase
    images_to_pdf: ImagesToPdfUseCase
    # -- organiser
    reorder_pages: ReorderPagesUseCase
    insert_pages: InsertPagesUseCase
    interleave_pdfs: InterleavePdfsUseCase
    crop_pages: CropPagesUseCase
    # -- optimiser
    compress_pdf: CompressPdfUseCase
    read_metadata: ReadMetadataUseCase
    write_metadata: WriteMetadataUseCase
    read_bookmarks: ReadBookmarksUseCase
    write_bookmarks: WriteBookmarksUseCase
    # -- personnaliser
    watermark_text: WatermarkTextUseCase
    stamp_image: StampImageUseCase
    sign_pdf: StampImageUseCase
    number_pages: NumberPagesUseCase
    scan_watermarks: ScanWatermarksUseCase
    remove_watermarks: RemoveWatermarksUseCase
    # -- extraire
    extract_images: ExtractImagesUseCase
    extract_text: ExtractTextUseCase
    # -- lot
    batch: BatchProcessUseCase


def build_use_cases(
    repository: PdfRepository | None = None,
    image_converter: ImageToPdfConverter | None = None,
    stamper: PdfStamper | None = None,
    optimizer: PdfOptimizer | None = None,
    archive: ArchiveWriter | None = None,
    remover: WatermarkRemover | None = None,
) -> UseCases:
    repository = repository or PyPdfRepository()
    image_converter = image_converter or PillowImageRepository()
    stamper = stamper or PyPdfStamper()
    optimizer = optimizer or PyPdfOptimizer()
    archive = archive or ZipArchiveWriter()
    remover = remover or PyPdfWatermarkRemover()
    return UseCases(
        count_pages=CountPagesUseCase(repository),
        split_pdf=SplitPdfUseCase(repository),
        extract_pages=ExtractPagesUseCase(repository),
        merge_pdfs=MergePdfsUseCase(repository),
        delete_pages=DeletePagesUseCase(repository),
        rotate_pages=RotatePagesUseCase(repository),
        landscape_pair=LandscapePairUseCase(repository),
        protect_pdf=ProtectPdfUseCase(repository),
        unlock_pdf=UnlockPdfUseCase(repository),
        images_to_pdf=ImagesToPdfUseCase(image_converter),
        reorder_pages=ReorderPagesUseCase(repository),
        insert_pages=InsertPagesUseCase(repository),
        interleave_pdfs=InterleavePdfsUseCase(repository),
        crop_pages=CropPagesUseCase(repository),
        compress_pdf=CompressPdfUseCase(optimizer),
        read_metadata=ReadMetadataUseCase(repository),
        write_metadata=WriteMetadataUseCase(repository),
        read_bookmarks=ReadBookmarksUseCase(repository),
        write_bookmarks=WriteBookmarksUseCase(repository),
        watermark_text=WatermarkTextUseCase(repository, stamper),
        stamp_image=StampImageUseCase(repository, stamper, default_pages="all"),
        sign_pdf=StampImageUseCase(
            repository, stamper, default_pages="last", kind=StampKind.SIGNATURE
        ),
        number_pages=NumberPagesUseCase(repository, stamper),
        scan_watermarks=ScanWatermarksUseCase(remover),
        remove_watermarks=RemoveWatermarksUseCase(remover),
        extract_images=ExtractImagesUseCase(repository),
        extract_text=ExtractTextUseCase(repository),
        batch=BatchProcessUseCase(repository, stamper, optimizer, archive),
    )
