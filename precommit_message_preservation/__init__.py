"All logic for the module."
import argparse
import collections
import datetime
import hashlib
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
from typing import List, Optional

LOGGER = logging.getLogger(__name__)
VERBOSE_MARKER = "# ------------------------ >8 ------------------------"

class MissingArgsError(Exception):
	"Indicates a required argument is missing."

SavedCommitMessage = collections.namedtuple("SavedCommitMessage", (
	"branch",
	"content",
	"created",
	"hookname",
	"repository",
))

def add_arguments(parser: argparse.ArgumentParser) -> None:
	"Add the necessary commandline arguments for this library."
	parser.add_argument("file", help="The path to the file containing the commit message.")

def clear_comments(content: str) -> str:
	"""Remove all comments from the commit message.

	Args:
		content: The content of the commit message.
	"""
	return "\n".join(l for l in content.split("\n") if not l.startswith("#"))


def clear_verbose_code(content: str) -> str:
	"""Remove the verbose code marker and all code below it.

	Args:
		content: The content of the commit message.
	Returns:
		The content without any lines after th verbose marker.
	"""
	parts = content.partition(VERBOSE_MARKER)
	return parts[0]


def connect_db() -> sqlite3.Connection:
	"Connect to the message database."
	path = xdg_cache_home() / "precommit-message-preservation.db"
	return sqlite3.connect(
		path.absolute(),
		detect_types=sqlite3.PARSE_DECLTYPES,
	)


def ensure_tables(connection: sqlite3.Connection) -> None:
	"Ensure the tables we need are present"
	cursor = connection.cursor()
	cursor.execute(
		"CREATE TABLE IF NOT EXISTS message ("
		"  branch STRING,"
		"  content STRING,"
		"  created timestamp,"
		"  hookname STRING,"
		"  repository STRING"
		")"
	)
	connection.commit()


def get_repository_branch() -> str:
	"""Get the name of the current branch for the git repository."""
	try:
		return subprocess.check_output(["git", "branch", "--show-current"]).decode("utf-8").strip()
	except subprocess.CalledProcessError as ex:
		LOGGER.warning("Failed to get the git branch: %s", ex)
	return "unknown"


def get_repository() -> Path:
	"""Get the fully qualified path of the root of the git repository.

	If we aren't running in a git repository just return the current working directory."""
	try:
		git_dir = subprocess.check_output(["git", "rev-parse", "--git-dir"]).decode("utf-8")
		return Path(os.path.abspath(os.path.dirname(git_dir)))
	except subprocess.CalledProcessError as ex:
		LOGGER.warning("Failed to call git rev-parse: %s", ex)
	return Path(os.path.abspath(os.curdir))


def main() -> None:
	"""Main entrypoint for pre-commit hook for restoring saved messages."""
	parser = argparse.ArgumentParser()
	add_arguments(parser)
	parser.add_argument("--dump",
		action="store_true",
		help="When present dump database contents and exit",
	)
	parser.add_argument("--any",
		action="store_true",
		help="When present do not filter by repository or branch.",
	)
	args = parser.parse_args()

	repository = None if args.any else get_repository()
	branch = None if args.any else get_repository_branch()
	old_messages = saved_commit_messages(
		repository,
		branch,
	)
	if args.dump:
		for message in old_messages:
			print(message)
		if not old_messages:
			print("No cached messages")
		return

	remove_message_cache(repository, branch)

	try:
		with open(args.file, "r") as input_:
			existing_content = input_.read()
	except FileNotFoundError:
		existing_content = ""

	content = "\n\n".join(
		"# Saved {} by {} hook\n{}".format(
			message.created.isoformat(),
			message.hookname,
			message.content,
		) for message in old_messages) + existing_content
	with open(args.file, "w") as output_:
		output_.write(content)


def remove_message_cache(repository: Optional[Path], branch: Optional[str]) -> None:
	"""Removes any files previously saved for caching failed messages.

	Args:
		repository: The absolute path to the repository root that this cache
		file is for.
		branch: The name of the branch the repository is checked out on.
	"""
	connection = connect_db()
	cursor = connection.cursor()
	query = "DELETE FROM message"
	if repository:
		if branch:
			query += " WHERE repository=? AND branch=?"
			params = [str(repository.absolute()), branch]
		else:
			query += " WHERE repository=?"
			params = [str(repository.absolute())]
	elif branch:
		query += " WHERE branch=?"
		params = [branch]
	cursor.execute(query, params)
	connection.commit()


def save_commit_message(message: str,
		repository: Path,
		branch: str,
		hookname: str) -> None:
	"""Get a previously cached commit message, if applicable.

	Args:
		message: The commit message to save.
		repository: The absolute path to the repository root that this cache
		file is for.
		branch: The name of the branch the repository is checked out on.
	"""
	connection = connect_db()
	ensure_tables(connection)
	cursor = connection.cursor()
	cursor.execute(
		"INSERT INTO message (branch, content, created, hookname, repository) VALUES(?, ?, ?, ?, ?)", (
			branch,
			message,
			datetime.datetime.now(),
			hookname,
			str(repository.absolute()),
		))
	connection.commit()

def saved_commit_messages(repository: Optional[Path], branch: Optional[str]) -> List[SavedCommitMessage]:
	"Get all the saved messages for a particular repository and branch"
	connection = connect_db()
	ensure_tables(connection)
	cursor = connection.cursor()

	query = "SELECT branch, content, created, hookname, repository FROM message"
	if repository:
		if branch:
			query += " WHERE repository=? AND branch=?"
			params = [str(repository), branch]
		else:
			query += " WHERE repository=?"
			params = [str(repository)]
	elif branch:
		query += " WHERE branch=?"
		params = [branch]
	else:
		params = []
	cursor.execute(query, params)
	return [
		SavedCommitMessage(
			branch=row[0],
			content=row[1],
			created=row[2],
			hookname=row[3],
			repository=row[4],
		) for row in cursor.fetchall()]


def xdg_cache_home() -> Path:
	"Get user's configured XDG_CACHE_HOME value."
	home = Path(os.path.expandvars("$HOME"))
	return Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))

class GetAndPreserveMessage():
	"""
	A context manager that handles saving and removing commit messages.

	In general clients of this library should use it as:

	try:
		with precommit_message_preservation.Preserve(content, hookname="my hook"):
			check(content)
	except:
		print("Message rejected because...")
		sys.exit()

	The check function should emit an exception if the commit message is
	rejected. This context manager will then preserve the message and offer
	it to the user in the next 'git commit' invocation.

	Args:
		args: The parsed arguments.
	"""
	def __init__(self, args: argparse.Namespace, hookname: str = "unknown"):
		if not hasattr(args, "file"):
			raise MissingArgsError(
				"The args provided had no value for 'args.file'. Likely this "
				"means the developer of the hook did not call "
				"precommit_message_preservation.add_arguments(parser) "
				"and therefore the argument wasn't added.")
		try:
			with open(args.file, "r") as input_:
				message = input_.read()
		except FileNotFoundError:
			message = ""

		no_code = clear_verbose_code(message)
		no_comments_or_code = clear_comments(no_code)

		self.branch = get_repository_branch()
		self.hookname = hookname
		self.message = no_comments_or_code
		self.repository = get_repository()

	def __enter__(self) -> str:
		save_commit_message(
			self.message,
			self.repository,
			self.branch,
			self.hookname)
		return self.message

	def __exit__(self, type_, value, traceback):
		if any([type_, value, traceback]):
			print("Commit message rejected. Original content:\n{}".format(self.message))
		else:
			remove_message_cache(self.repository, self.branch)
		return False
