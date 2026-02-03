"""Tests for django_dolt.models and admin integration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.contrib.admin.sites import AdminSite

from django_dolt.admin import BranchAdmin, CommitAdmin, RemoteAdmin
from django_dolt.models import Branch, Commit, Remote


class TestBranchModel:
    """Test Branch model definition."""

    def test_meta_options(self) -> None:
        assert Branch._meta.managed is False
        assert Branch._meta.db_table == "dolt_branches"
        assert Branch._meta.verbose_name == "Branch"
        assert Branch._meta.verbose_name_plural == "Branches"

    def test_str_representation(self) -> None:
        branch = Branch(name="main", hash="abc123")
        assert str(branch) == "main"

    def test_primary_key_is_name(self) -> None:
        pk_field = Branch._meta.pk
        assert pk_field is not None
        assert pk_field.name == "name"


class TestCommitModel:
    """Test Commit model definition."""

    def test_meta_options(self) -> None:
        assert Commit._meta.managed is False
        assert Commit._meta.db_table == "dolt_log"
        assert Commit._meta.verbose_name == "Commit"
        assert Commit._meta.verbose_name_plural == "Commits"

    def test_str_representation(self) -> None:
        commit = Commit(
            commit_hash="abc123def456789",
            message="Add new feature for users",
        )
        assert str(commit) == "abc123de - Add new feature for users"

    def test_str_truncates_long_message(self) -> None:
        long_message = "A" * 100
        commit = Commit(commit_hash="abc123def456789", message=long_message)
        result = str(commit)
        assert len(result) < 70  # 8 char hash + " - " + 50 chars

    def test_primary_key_is_commit_hash(self) -> None:
        pk_field = Commit._meta.pk
        assert pk_field is not None
        assert pk_field.name == "commit_hash"


class TestRemoteModel:
    """Test Remote model definition."""

    def test_meta_options(self) -> None:
        assert Remote._meta.managed is False
        assert Remote._meta.db_table == "dolt_remotes"
        assert Remote._meta.verbose_name == "Remote"
        assert Remote._meta.verbose_name_plural == "Remotes"

    def test_str_representation(self) -> None:
        remote = Remote(name="origin", url="https://example.com/repo")
        assert str(remote) == "origin"

    def test_primary_key_is_name(self) -> None:
        pk_field = Remote._meta.pk
        assert pk_field is not None
        assert pk_field.name == "name"


class TestBranchAdmin:
    """Test BranchAdmin configuration."""

    @pytest.fixture
    def admin_instance(self) -> BranchAdmin:
        return BranchAdmin(Branch, AdminSite())

    def test_list_display(self, admin_instance: BranchAdmin) -> None:
        assert "name" in admin_instance.list_display
        assert "hash_short" in admin_instance.list_display
        assert "latest_committer" in admin_instance.list_display

    def test_hash_short_truncates(self, admin_instance: BranchAdmin) -> None:
        branch = Branch(hash="abc123def456789")
        result = admin_instance.hash_short(branch)
        assert result == "abc123de"

    def test_is_read_only(self, admin_instance: BranchAdmin) -> None:
        request = MagicMock()
        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_change_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False


class TestCommitAdmin:
    """Test CommitAdmin configuration."""

    @pytest.fixture
    def admin_instance(self) -> CommitAdmin:
        return CommitAdmin(Commit, AdminSite())

    def test_list_display(self, admin_instance: CommitAdmin) -> None:
        assert "hash_short" in admin_instance.list_display
        assert "committer" in admin_instance.list_display
        assert "date" in admin_instance.list_display
        assert "message_preview" in admin_instance.list_display

    def test_hash_short_truncates(self, admin_instance: CommitAdmin) -> None:
        commit = Commit(commit_hash="abc123def456789")
        result = admin_instance.hash_short(commit)
        assert result == "abc123de"

    def test_message_preview_short_message(
        self, admin_instance: CommitAdmin
    ) -> None:
        commit = Commit(message="Short message")
        result = admin_instance.message_preview(commit)
        assert result == "Short message"

    def test_message_preview_long_message(
        self, admin_instance: CommitAdmin
    ) -> None:
        commit = Commit(message="A" * 100)
        result = admin_instance.message_preview(commit)
        assert result == "A" * 60 + "..."

    def test_ordering(self, admin_instance: CommitAdmin) -> None:
        assert admin_instance.ordering == ["-date"]

    def test_is_read_only(self, admin_instance: CommitAdmin) -> None:
        request = MagicMock()
        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_change_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False


class TestRemoteAdmin:
    """Test RemoteAdmin configuration."""

    @pytest.fixture
    def admin_instance(self) -> RemoteAdmin:
        return RemoteAdmin(Remote, AdminSite())

    def test_list_display(self, admin_instance: RemoteAdmin) -> None:
        assert "name" in admin_instance.list_display
        assert "url" in admin_instance.list_display

    def test_is_read_only(self, admin_instance: RemoteAdmin) -> None:
        request = MagicMock()
        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_change_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False
