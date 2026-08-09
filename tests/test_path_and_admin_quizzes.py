"""Tests for coding path and teacher quiz membership APIs."""

from backend.models.user import User
from tests.helpers import make_question, make_quiz_with_questions, register_and_login_headers


def _auth_headers(client, database_session, username: str) -> dict[str, str]:
    return register_and_login_headers(client, database_session, username)


def _make_admin(client, database_session, username: str) -> dict[str, str]:
    headers = _auth_headers(client, database_session, username)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()
    return headers


def test_admin_can_build_quiz_membership(client, database_session) -> None:
    headers = _make_admin(client, database_session, "quiz_builder")
    q1 = make_question(
        database_session,
        title="Bank Q1",
        description="MCQ",
        topics=["basics"],
        choices=["a", "b"],
        correct_answer="a",
    )
    q2 = make_question(
        database_session,
        title="Bank Q2",
        description="Coding",
        question_type="coding",
        topics=["basics", "loops"],
        starter_code='print("x")\n',
        test_cases=[{"stdin": "", "expected_stdout": "x"}],
    )
    database_session.commit()

    created = client.post(
        "/api/v1/admin/quizzes",
        headers=headers,
        json={
            "title": "Mixed Pack",
            "description": "MCQ + coding",
            "is_timed": True,
            "duration_seconds": 90,
        },
    )
    assert created.status_code == 201
    quiz_id = created.json()["id"]

    membership = client.put(
        f"/api/v1/admin/quizzes/{quiz_id}/questions",
        headers=headers,
        json={"question_ids": [q1.id, q2.id]},
    )
    assert membership.status_code == 200
    assert membership.json()["question_ids"] == [q1.id, q2.id]
    assert set(membership.json()["topics"]) == {"basics", "loops"}


def test_admin_can_create_topic(client, database_session) -> None:
    headers = _make_admin(client, database_session, "topic_builder")
    response = client.post(
        "/api/v1/admin/topics",
        headers=headers,
        json={"name": "Recursion"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "recursion"


def test_coding_path_lists_modules_and_levels(client, database_session) -> None:
    headers = _make_admin(client, database_session, "path_builder")
    student = _auth_headers(client, database_session, "path_student")

    coding = make_question(
        database_session,
        title="Path Hello",
        description="Print hi",
        question_type="coding",
        topics=["basics"],
        starter_code='print("hi")\n',
        test_cases=[{"stdin": "", "expected_stdout": "hi"}],
    )
    database_session.commit()

    classroom = client.post(
        "/api/v1/classes",
        headers=headers,
        json={
            "title": "Path Class",
            "description": "Coding path via class",
            "visibility": "public",
        },
    ).json()
    module = client.post(
        "/api/v1/admin/modules",
        headers=headers,
        json={
            "class_id": classroom["id"],
            "title": "Module Basics",
            "description": "Start here",
            "position": 0,
            "difficulty_label": "Beginner",
        },
    ).json()
    assert module["class_id"] == classroom["id"]
    blocks = client.put(
        f"/api/v1/admin/modules/{module['id']}/blocks",
        headers=headers,
        json={
            "blocks": [
                {
                    "type": "lecture",
                    "payload": {"markdown": "Start here"},
                },
                {
                    "type": "coding",
                    "payload": {},
                    "question_id": coding.id,
                },
            ]
        },
    )
    assert blocks.status_code == 200
    assert [b["type"] for b in blocks.json()["blocks"]] == ["lecture", "coding"]

    # Global path is class-scoped and returns empty.
    global_path = client.get("/api/v1/path", headers=student)
    assert global_path.status_code == 200
    assert global_path.json() == []
    client.post(
        "/api/v1/classes/enroll",
        headers=student,
        json={"code": classroom["enrollment_code"]},
    )

    path = client.get(
        f"/api/v1/classes/{classroom['id']}/path",
        headers=student,
    )
    assert path.status_code == 200
    body = path.json()[0]
    assert body["title"] == "Module Basics"
    assert body["blocks"][0]["type"] == "lecture"
    assert body["blocks"][1]["question_id"] == coding.id
    assert body["levels"][0]["question_id"] == coding.id
    assert body["levels"][0]["is_completed"] is False


def test_module_can_include_multimedia_block(client, database_session) -> None:
    headers = _make_admin(client, database_session, "media_block_teacher")
    classroom = client.post(
        "/api/v1/classes",
        headers=headers,
        json={
            "title": "Media Class",
            "description": "Has media blocks",
            "visibility": "private",
        },
    ).json()
    module = client.post(
        "/api/v1/admin/modules",
        headers=headers,
        json={
            "class_id": classroom["id"],
            "title": "Chapter with video",
            "description": "",
        },
    ).json()
    updated = client.put(
        f"/api/v1/admin/modules/{module['id']}/blocks",
        headers=headers,
        json={
            "blocks": [
                {
                    "type": "lecture",
                    "payload": {"markdown": "Intro"},
                    "question_id": None,
                },
                {
                    "type": "media",
                    "payload": {
                        "title": "Demo clip",
                        "url": "https://youtu.be/abcdefghijk",
                        "kind": "youtube",
                        "label": None,
                    },
                    "question_id": None,
                },
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    types = [block["type"] for block in updated.json()["blocks"]]
    assert types == ["lecture", "media"]
    assert updated.json()["blocks"][1]["payload"]["title"] == "Demo clip"


def test_create_module_appends_when_position_taken(
    client, database_session
) -> None:
    headers = _make_admin(client, database_session, "mod_pos_teacher")
    classroom = client.post(
        "/api/v1/classes",
        headers=headers,
        json={
            "title": "Pos Class",
            "description": "Positions",
            "visibility": "public",
        },
    ).json()
    first = client.post(
        "/api/v1/admin/modules",
        headers=headers,
        json={
            "class_id": classroom["id"],
            "title": "First Module",
            "description": "",
            "position": 0,
        },
    )
    assert first.status_code == 201
    assert first.json()["blocks"][0]["type"] == "lecture"
    # Intentionally request a taken position — should append, not 500.
    second = client.post(
        "/api/v1/admin/modules",
        headers=headers,
        json={
            "class_id": classroom["id"],
            "title": "Second Module",
            "description": "",
            "position": 0,
        },
    )
    assert second.status_code == 201
    assert second.json()["position"] == 1


def test_clone_quiz_does_not_mutate_source(client, database_session) -> None:
    owner = _make_admin(client, database_session, "quiz_owner")
    other = _make_admin(client, database_session, "quiz_other")
    q1 = make_question(
        database_session,
        title="Shared MCQ",
        description="Pick a",
        topics=["basics"],
        choices=["a", "b"],
        correct_answer="a",
        visibility="public",
    )
    database_session.commit()

    created = client.post(
        "/api/v1/admin/quizzes",
        headers=owner,
        json={
            "title": "Bank Quiz",
            "description": "Source quiz",
            "visibility": "public",
        },
    )
    assert created.status_code == 201
    source_id = created.json()["id"]
    client.put(
        f"/api/v1/admin/quizzes/{source_id}/questions",
        headers=owner,
        json={"question_ids": [q1.id]},
    )

    cloned = client.post(
        f"/api/v1/admin/quizzes/{source_id}/clone",
        headers=other,
    )
    assert cloned.status_code == 201
    copy = cloned.json()
    assert copy["id"] != source_id
    assert copy["visibility"] == "private"
    assert copy["source_quiz_id"] == source_id
    assert copy["question_ids"] != [q1.id]
    assert len(copy["question_ids"]) == 1

    source = client.get("/api/v1/admin/quizzes", headers=owner).json()
    source_row = next(item for item in source if item["id"] == source_id)
    assert source_row["question_ids"] == [q1.id]
    assert source_row["title"] == "Bank Quiz"


def test_private_quizzes_hidden_from_other_teachers(client, database_session) -> None:
    owner = _make_admin(client, database_session, "private_owner")
    other = _make_admin(client, database_session, "private_viewer")

    private = client.post(
        "/api/v1/admin/quizzes",
        headers=owner,
        json={
            "title": "Secret Drill",
            "description": "Mine only",
            "visibility": "private",
        },
    )
    assert private.status_code == 201
    private_id = private.json()["id"]

    shared = client.post(
        "/api/v1/admin/quizzes",
        headers=owner,
        json={
            "title": "Open Drill",
            "description": "Shared bank",
            "visibility": "public",
        },
    )
    assert shared.status_code == 201
    shared_id = shared.json()["id"]

    other_list = client.get("/api/v1/admin/quizzes", headers=other).json()
    other_ids = {item["id"] for item in other_list}
    assert private_id not in other_ids
    assert shared_id in other_ids

    owner_list = client.get("/api/v1/admin/quizzes", headers=owner).json()
    owner_ids = {item["id"] for item in owner_list}
    assert private_id in owner_ids
    assert shared_id in owner_ids
