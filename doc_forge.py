from pathlib import Path
from docx import Document
from pydantic import BaseModel, Field


class KeyValueRow(BaseModel):
    metric: str = Field(description="Name of the metric or table key")
    value: str = Field(description="Value or status of the metric")


class DocSection(BaseModel):
    heading: str = Field(description="Section heading title")
    body: str = Field(description="Main paragraph text for this section")
    bullet_points: list[str] = Field(
        default_factory=list,
        description="Optional bulleted list items under this section",
    )


class DocumentSpec(BaseModel):
    filename: str = Field(description="Output filename ending in .docx")
    title: str = Field(description="Main title of the document")
    sections: list[DocSection] = Field(description="Ordered list of document sections")
    summary_table: list[KeyValueRow] = Field(
        default_factory=list,
        description="Optional summary table of key-value metrics at the end of the document",
    )


def compile_docx(spec: DocumentSpec, output_dir: str = ".") -> str:
    """Compiles a validated DocumentSpec into a native Word/LibreOffice .docx file."""

    out_folder = Path(output_dir)
    out_folder.mkdir(parents=True, exist_ok=True)

    clean_name = (
        spec.filename
        if spec.filename.endswith(".docx")
        else f"{spec.filename}.docx"
    )

    out_path = out_folder / clean_name

    doc = Document()

    # TODO 1: Title and Sections

    # Add main title
    doc.add_heading(spec.title, 0)

    # Add sections
    for sec in spec.sections:
        doc.add_heading(sec.heading, level=1)

        # Add section body
        doc.add_paragraph(sec.body)

        # Add bullet points
        for bullet in sec.bullet_points:
            doc.add_paragraph(bullet, style="List Bullet")

    # TODO 2: Optional Summary Table

    if spec.summary_table:
        doc.add_heading("Summary Metrics", level=1)

        # Create table with 2 columns and 1 header row
        table = doc.add_table(rows=1, cols=2)

        # Set table headers
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Metric"
        hdr_cells[1].text = "Value"

        # Populate table
        for item in spec.summary_table:
            row_cells = table.add_row().cells

            row_cells[0].text = item.metric
            row_cells[1].text = item.value

    # TODO 3: Save and Return Path

    doc.save(str(out_path))

    return str(out_path.resolve())


if __name__ == "__main__":
    sample_spec = DocumentSpec(
        filename="aether_architecture_brief.docx",
        title="Aether-OS: Offline Linux Assistant Brief",
        sections=[
            DocSection(
                heading="1. Executive Overview",
                body="Aether-OS is an offline-capable Linux system steward powered by local LLM inference and Pydantic tool schemas.",
                bullet_points=[
                    "SHA-256 content-addressed duplicate file elimination",
                    "Transactional .aether_trash staging vault with manifest recovery",
                    "Headless LibreOffice / Word (.docx) document generation",
                ],
            ),
        ],
        summary_table=[
            KeyValueRow(metric="Target VRAM Budget", value="4.7 GB (Q4_K_M)"),
            KeyValueRow(metric="Primary GPU", value="NVIDIA RTX 4060 Laptop (8GB)"),
            KeyValueRow(metric="Storage Safety", value="Reversible Trash Manifest"),
        ],
    )

    saved_path = compile_docx(sample_spec, output_dir="sandbox_dir")

    print(f"✅ Compiled LibreOffice/Word Document at: {saved_path}")