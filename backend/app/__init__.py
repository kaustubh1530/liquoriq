# Import all models here so SQLAlchemy resolves relationships correctly.
# Any file that imports one model must see all models — this guarantees that.
from app.models.user import User  # noqa: F401
from app.models.store import Store  # noqa: F401
from app.models.uploaded_report import UploadedReport, ReportSource, ReportStatus  # noqa: F401
from app.models.normalized_sale import NormalizedSale  # noqa: F401