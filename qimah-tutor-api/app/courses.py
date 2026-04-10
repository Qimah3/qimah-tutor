"""Course/topic → Drive folder lookup from courses.yaml."""

import yaml
from pathlib import Path

_courses = None


def load_courses(path: str = None) -> dict:
    """Load courses.yaml (lazy singleton). Pass *path* to force-reload from a specific file."""
    global _courses
    if _courses is not None and path is None:
        return _courses
    config_path = Path(path) if path else Path(__file__).parent.parent / "courses.yaml"
    with open(config_path) as f:
        _courses = yaml.safe_load(f)
    return _courses


def lookup_folder(course_id: int, topic_id: int) -> str | None:
    """Return the drive_folder_id for a course/topic pair, or None if not mapped."""
    data = load_courses()
    for course in data.get("courses", []):
        if course.get("course_id") != course_id:
            continue
        for topic in course.get("topics", []):
            if topic.get("topic_id") == topic_id:
                return topic.get("drive_folder_id")
    return None
