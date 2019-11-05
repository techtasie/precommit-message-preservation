import contextlib
import os
import subprocess
import typing
import unittest
import unittest.mock

import precommit_message_preservation as pmp

@contextlib.contextmanager
def fake_repository(repository_root: typing.Text, repository_branch: typing.Text):
	"Set up a fake repository root and branch."
	with unittest.mock.patch("precommit_message_preservation.get_repository_root", return_value=repository_root):
		with unittest.mock.patch("precommit_message_preservation.get_repository_branch", return_value=repository_branch):
			yield


@contextlib.contextmanager
def known_xdg_cache(location: typing.Text):
	with unittest.mock.patch("precommit_message_preservation.XDG_CACHE_HOME", location):
		yield


class Tests(unittest.TestCase):
	def test_get_cached_message(self):
		"Test we can get the cached message in its simplest form"
		with fake_repository("/tmp/repo", "master"):
			with unittest.mock.patch("precommit_message_preservation.get_content", return_value="some content") as get_content:
				message = pmp.get_cached_message()
				self.assertEqual(message, "some content")
				get_content.assert_called()
				self.assertTrue(get_content.call_args[0][0].endswith("precommit-message-preservation/repo-b6fe87a9/master.txt"))
			
	def test_get_cached_message_repository_branch(self):
		"Test we can get the cached message for a specific repository."
		with unittest.mock.patch("precommit_message_preservation.get_content", return_value="some content") as get_content:
			message = pmp.get_cached_message("/tmp/repo", "master")
			self.assertEqual(message, "some content")
			get_content.assert_called()
			self.assertTrue(get_content.call_args[0][0].endswith("precommit-message-preservation/repo-b6fe87a9/master.txt"))

	def test_get_cache_file_path(self):
		"Test getting the cache file patch for a specific repository and branch."
		path = pmp.get_cache_file_path("/tmp/repo2", "master")
		self.assertTrue(path.endswith("precommit-message-preservation/repo2-73f71b32/master.txt"))


	def test_get_cache_file_path_xdg_config(self):
		"Test getting the cache file patch for a specific repository and branch with custom xdg."
		with known_xdg_cache("/tmp/xdg-cache"):
			path = pmp.get_cache_file_path("/tmp/repo3", "master")
			self.assertEqual(path, "/tmp/xdg-cache/precommit-message-preservation/repo3-41d4ff88/master.txt")


	def test_get_content(self):
		"Test getting content of a file that exists."
		with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data="some data")) as mock_file:
			content = pmp.get_content("some-file.txt")
			self.assertEqual(content, "some data")

	def test_get_content_failed(self):
		"Test getting content of a file that does not exist."
		with unittest.mock.patch("builtins.open", side_effect=OSError()) as mock_file:
			content = pmp.get_content("some-file.txt")
			self.assertEqual(content, "")

	def test_get_repository_branch(self):
		"Get the repository branch."
		with unittest.mock.patch("subprocess.check_output", autospec=subprocess.check_output, return_value=b"develop") as check_output:
			root = pmp.get_repository_branch()
			check_output.assert_called_with(["git", "branch"])
			self.assertEqual(root, "develop")

	def test_get_repository_branch_failed(self):
		"Fail to get the repository branch."
		with unittest.mock.patch("subprocess.check_output", autospec=subprocess.check_output, side_effect=subprocess.CalledProcessError(1, "git")) as check_output:
			root = pmp.get_repository_branch()
			check_output.assert_called_with(["git", "branch"])
			self.assertEqual(root, "unknown")

	def test_get_repository_root(self):
		"Get the repository root."
		with unittest.mock.patch("subprocess.check_output", autospec=subprocess.check_output, return_value=b"/some/repository/.git") as check_output:
			root = pmp.get_repository_root()
			check_output.assert_called_with(["git", "rev-parse", "--git-dir"])
			self.assertEqual(root, "/some/repository")

	def test_get_repository_root_failed(self):
		"Fail to get the repository root."
		with unittest.mock.patch("subprocess.check_output", autospec=subprocess.check_output, side_effect=subprocess.CalledProcessError(1, "git")) as check_output:
			root = pmp.get_repository_root()
			check_output.assert_called_with(["git", "rev-parse", "--git-dir"])
			self.assertEqual(root, os.path.abspath("."))

	def test_remove_message_cache(self):
		"Remove the message cache."
		with unittest.mock.patch("os.path.exists", return_value=True) as exists:
			with unittest.mock.patch("os.remove") as remove:
				with known_xdg_cache("/tmp/xdg-cache"):
					pmp.remove_message_cache("repo4", "release-1.3")
					exists.assert_called()
					remove.assert_called_with("/tmp/xdg-cache/precommit-message-preservation/repo4-8188c7ca/release-1.3.txt")

	def test_remove_message_cache_not_exists(self):
		"Try to memove the message cache when it does not exist."
		with unittest.mock.patch("os.path.exists", return_value=False) as exists:
			with known_xdg_cache("/tmp/xdg-cache"):
				pmp.remove_message_cache("repo5", "cafebabe")
				exists.assert_called_with("/tmp/xdg-cache/precommit-message-preservation/repo5-9825b024/cafebabe.txt")

	def test_save_commit_message(self):
		"Save a commit message."
		with fake_repository("my-repo", "my-branch"):
			with known_xdg_cache("/tmp/xdg-cache"):
				with unittest.mock.patch("os.makedirs") as makedirs:
					mock_open = unittest.mock.mock_open()
					with unittest.mock.patch("builtins.open", mock_open, create=True):
						pmp.save_commit_message("some important content")
						makedirs.assert_called_with("/tmp/xdg-cache/precommit-message-preservation/my-repo-aa38d26c", exist_ok=True)
						mock_open.assert_called_once_with("/tmp/xdg-cache/precommit-message-preservation/my-repo-aa38d26c/my-branch.txt", "w")
						mock_open().write.assert_called_once_with("some important content")

	def test_save_commit_message_specific_repository(self):
		"Save a commit message to a specific repository."
		with known_xdg_cache("/tmp/xdg-cache"):
			with unittest.mock.patch("os.makedirs") as makedirs:
				mock_open = unittest.mock.mock_open()
				with unittest.mock.patch("builtins.open", mock_open, create=True):
					pmp.save_commit_message("some important content", "my-repo", "my-branch")
					makedirs.assert_called_with("/tmp/xdg-cache/precommit-message-preservation/my-repo-aa38d26c", exist_ok=True)
					mock_open.assert_called_once_with("/tmp/xdg-cache/precommit-message-preservation/my-repo-aa38d26c/my-branch.txt", "w")
					mock_open().write.assert_called_once_with("some important content")

	def test_message_preservation_success(self):
		"Message cache should be removed on successful exit from MessagePreservation"
		with fake_repository("some-repo", "a-branch"):
			with unittest.mock.patch("precommit_message_preservation.remove_message_cache") as remove:
				with pmp.MessagePreservation("some message"):
					pass
				remove.assert_called_with("some-repo", "a-branch")

	def test_message_preservation_failure(self):
		"Message cache should be saved on unsuccessful exit from MessagePreservation"
		with fake_repository("some-repo", "a-branch"):
			with unittest.mock.patch("precommit_message_preservation.save_commit_message") as save:
				with self.assertRaises(Exception):
					with pmp.MessagePreservation("some message"):
						raise Exception("for testing.")
					save.assert_called_with("some-repo", "a-branch")
