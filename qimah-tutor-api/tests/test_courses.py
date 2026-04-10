"""Tests for app/courses.py — course/topic folder lookup."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.courses as courses_mod
from app.courses import load_courses, lookup_folder


SAMPLE_YAML = os.path.join(os.path.dirname(__file__), "fixtures", "courses_sample.yaml")


def setup_function():
    """Reset cached courses before each test."""
    courses_mod._courses = None


def test_lookup_found():
    """Known course+topic returns the correct drive_folder_id."""
    load_courses(SAMPLE_YAML)
    result = lookup_folder(101, 10)
    assert result == "1aBcDeFgHiJkLmNoPqRsT"


def test_lookup_second_topic():
    """Second topic in same course returns its own folder ID."""
    load_courses(SAMPLE_YAML)
    result = lookup_folder(101, 11)
    assert result == "2xYzAbCdEfGhIjKlMnOp"


def test_lookup_different_course():
    """Topic in a different course resolves correctly."""
    load_courses(SAMPLE_YAML)
    result = lookup_folder(102, 20)
    assert result == "3qRsTuVwXyZaBcDeFgHi"


def test_lookup_unknown_course():
    """Bad course_id returns None."""
    load_courses(SAMPLE_YAML)
    assert lookup_folder(999, 10) is None


def test_lookup_unknown_topic():
    """Good course_id, bad topic_id returns None."""
    load_courses(SAMPLE_YAML)
    assert lookup_folder(101, 999) is None


def test_load_caches():
    """Second call without path returns the same cached object."""
    first = load_courses(SAMPLE_YAML)
    second = load_courses()
    assert first is second
