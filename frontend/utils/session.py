"""Streamlit session helpers for authentication state."""

from __future__ import annotations

import streamlit as st

from frontend.utils.browser_auth import (
    clear_persisted_auth,
    persist_auth,
    restore_auth_from_browser,
)


def init_session_state() -> None:
    """Create auth keys and restore from browser cookies after refresh."""

    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "auth_restored" not in st.session_state:
        st.session_state.auth_restored = False

    if not st.session_state.auth_restored and not st.session_state.access_token:
        token, user = restore_auth_from_browser()
        if token and user:
            st.session_state.access_token = token
            st.session_state.current_user = user
        st.session_state.auth_restored = True


def is_logged_in() -> bool:
    """Return True when the user has a stored access token."""

    init_session_state()
    return bool(st.session_state.access_token)


def save_auth_session(access_token: str, user: dict) -> None:
    """Persist login details in session state and browser cookies."""

    init_session_state()
    st.session_state.access_token = access_token
    st.session_state.current_user = user
    st.session_state.auth_restored = True
    persist_auth(access_token, user)


def clear_auth_session() -> None:
    """Remove login details from session state and browser cookies."""

    init_session_state()
    st.session_state.access_token = None
    st.session_state.current_user = None
    clear_persisted_auth()


def get_access_token() -> str | None:
    """Return the stored JWT access token, if any."""

    init_session_state()
    return st.session_state.access_token


def refresh_user_profile() -> dict | None:
    """Re-validate the token with /me and refresh cached user data."""

    from frontend.utils.api import APIError, get_current_user

    token = get_access_token()
    if not token:
        return None
    try:
        user = get_current_user(token)
    except APIError:
        clear_auth_session()
        return None
    save_auth_session(token, user)
    return user
