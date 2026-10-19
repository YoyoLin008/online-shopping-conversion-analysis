"""Execute the analysis and typeset its source and real output in two pages."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "coding_essay.py"
OUTPUT = ROOT / "Yunya_Lin_UChicago_Coding_Essay.pdf"
RESULTS = ROOT / "support/results"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--python", default=sys.executable,
                    help="Python executable used to run the analysis")
args = parser.parse_args()
RESULTS.mkdir(parents=True, exist_ok=True)

# Run the standalone file; fail the build if Python reports an error.
started = datetime.now(ZoneInfo("America/Chicago"))
result = subprocess.run([args.python, str(SOURCE)], cwd=ROOT,
                        capture_output=True, text=True, check=True)
printed = result.stdout
print(printed, end="")
if result.stderr:
    print(result.stderr, file=sys.stderr, end="")
(RESULTS / "console_output.txt").write_text(printed)
env_code = (
    "import sys,json,numpy,pandas,matplotlib; "
    "print(json.dumps({'python':sys.version.split()[0], "
    "'numpy':numpy.__version__, 'pandas':pandas.__version__, "
    "'matplotlib':matplotlib.__version__}))"
)
versions = json.loads(subprocess.check_output([args.python, "-c", env_code],
                                               text=True))
record = ["Execution record", f"Started: {started.isoformat()}",
          f"Finished: {datetime.now(ZoneInfo('America/Chicago')).isoformat()}",
          f"Python executable: {args.python}", "Command: python coding_essay.py",
          "Exit status: 0", "Versions: " + json.dumps(versions, sort_keys=True)]
for path in [SOURCE, ROOT / "support/data/online_shoppers_intention.csv",
             RESULTS / "console_output.txt", RESULTS / "conversion_comparison.png"]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record.append(f"SHA-256 {path.relative_to(ROOT)}: {digest}")
(RESULTS / "execution_record.txt").write_text("\n".join(record) + "\n")

# Use the actual Times New Roman and Courier New fonts installed on this Mac.
fonts = Path("/System/Library/Fonts/Supplemental")
for name, filename in [("TNR", "Times New Roman.ttf"),
                       ("TNR-Bold", "Times New Roman Bold.ttf"),
                       ("Code", "Courier New.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
pdfmetrics.registerFontFamily("TNR", normal="TNR", bold="TNR-Bold",
                              italic="TNR", boldItalic="TNR-Bold")
c = canvas.Canvas(str(OUTPUT), pagesize=(612, 792), pageCompression=1)
c.setTitle("Purchase Conversion by Visitor Type")
c.setAuthor("Yunya Lin")
c.setSubject("Python analysis of UCI online shopping sessions")
M, WIDTH = 54, 504
lines = SOURCE.read_text().splitlines()
split = next(i for i, line in enumerate(lines)
             if line.startswith("# Intervals describe"))

def text(value, x, y, font="TNR", size=11):
    c.setFillColorRGB(0, 0, 0)
    c.setFont(font, size)
    c.drawString(x, y, value)

def paragraph(value, top, size=11, leading=13):
    style = ParagraphStyle("body", fontName="TNR", fontSize=size,
                           leading=leading, textColor="black")
    p = Paragraph(value, style)
    _, height = p.wrap(WIDTH, 792)
    p.drawOn(c, M, top-height)
    return top-height

def code(block, top, size=9.5, leading=11.0):
    obj = c.beginText(M, top)
    obj.setFont("Code", size)
    obj.setLeading(leading)
    obj.setFillColorRGB(0, 0, 0)
    for line in block:
        assert pdfmetrics.stringWidth(line, "Code", size) <= WIDTH, line
        obj.textLine(line)
    c.drawText(obj)
    return top-len(block)*leading

def page_number(number):
    c.setFont("TNR", 10)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(306, 28, str(number))

# Page 1: a modest title and the data preparation, function and reporting code.
c.setFont("TNR-Bold", 14)
c.drawCentredString(306, 744, "Purchase Conversion by Visitor Type")
c.setFont("TNR", 11)
c.drawCentredString(306, 726, "Yunya Lin")
y = paragraph(
    "Does month composition explain the purchase-rate difference between new "
    "and returning visitors? The UCI data contain 12,330 sessions from distinct "
    "users. Revenue records whether a purchase occurred, not its monetary value.",
    709, size=11, leading=13)
y = code(lines[:split], y-17)
assert y > 50, y
page_number(1)
c.showPage()

# Page 2: plotting code, captured Python output and the actual Matplotlib figure.
y = code(lines[split:], 742)
y -= 8
text("Output", M, y, font="TNR-Bold", size=11)
y = code(printed.rstrip().splitlines(), y-16, size=9.5, leading=11.5)
y -= 9
chart_height = WIDTH * 2.4 / 7.2
c.drawImage(str(RESULTS / "conversion_comparison.png"), M, y-chart_height,
            width=WIDTH, height=chart_height, mask="auto")
y -= chart_height+6
y = paragraph(
    "Figure 1. Purchase rates by visitor type. Circles and whiskers show "
    "observed rates and 95% Wilson intervals; open diamonds show point estimates "
    "using the pooled monthly distribution of the retained sample.",
    y, size=10, leading=12)
y = paragraph(
    "The observed gap is 10.98 percentage points; giving both groups the same "
    "month mix leaves a 10.67-point gap. Month composition alone therefore "
    "does not account for the difference in this sample. This comparison is "
    "descriptive, not causal: visitor characteristics may differ, and February "
    "has only one new visitor. No uncertainty interval is estimated for the "
    "month-standardized rates.", y-10, size=11, leading=13)
y = paragraph(
    "Source: Sakar, C., and Kastro, Y. (2018). Online Shoppers Purchasing "
    "Intention Dataset. UCI Machine Learning Repository. "
    "https://doi.org/10.24432/C5F88Q. CC BY 4.0.",
    y-10, size=10, leading=12)
assert y > 50, y
page_number(2)
c.save()
print(f"Saved {OUTPUT.name}; page 2 ends at {y:.1f} pt.")
