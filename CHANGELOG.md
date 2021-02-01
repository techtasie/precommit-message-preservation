# Changelog

# 1.2

* Add separator between cached messages and existing message
* Add log at `$XDG_CACHE_HOME/precommit-message-preservation.log`

# 1.1

 * Avoid conflict with multiple commit-msg hooks saving messages at once.

# 1.0

 * Move to using a sqlite DB rather than the filesystem to save messages.
 * Rename context manager, require passing in the argument parser.
 * Save message on context manager entrance, not an failure.
 * Remove dependency on XDG library.
 * Use pathlib.Path instead of strings

# 0.6

Add type hinting to the library distribution

# 0.5

Properly handle commit messages with empty lines

# 0.4

Don't save comments in the commit message or verbose code

# 0.3

Strip whitespace that git adds, use the correct git command

# 0.2

Initial release
