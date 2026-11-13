"""S-04: PROJECT_STATE.md keeps the structure the handoff process depends on."""

import re

REQUIRED_SECTIONS = [
    "Resume here",
    "Status",
    "Architecture decisions",
    "Completed milestones",
    "Verified tests",
    "Known bugs",
    "Security limitations",
    "Assumptions",
    "Outstanding tasks and open decisions for the owner",
    "Environment notes",
]

TASK_IDS = [f"P1-{n:02d}" for n in range(20)]
TASK_STATES = {"todo", "in progress", "done", "blocked"}


def test_required_sections_in_order(root):
    text = (root / "PROJECT_STATE.md").read_text()
    headings = re.findall(r"^## \d+\. (.+)$", text, flags=re.MULTILINE)
    assert headings == REQUIRED_SECTIONS


def test_every_task_has_a_valid_state(root):
    text = (root / "PROJECT_STATE.md").read_text()
    rows = dict(re.findall(r"^\| (P1-\d{2}) \| [^|]+ \| ([^|]+) \|", text, flags=re.MULTILINE))
    assert sorted(rows) == TASK_IDS
    bad = {task: state for task, state in rows.items() if state.strip() not in TASK_STATES}
    assert not bad, f"invalid task states: {bad}"


def test_resume_section_names_branch_and_next_task(root):
    text = (root / "PROJECT_STATE.md").read_text()
    resume = text.split("## 1. Resume here", 1)[1].split("\n## ", 1)[0]
    assert "**Branch:**" in resume
    assert "**Next task:**" in resume
