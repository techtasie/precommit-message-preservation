# precommit-message-perservation

This is a simple library that makes it easier to code hooks for [pre-commit](https://pre-commit.com) that validate commit messages that preserve the commit message on failure.
In other words, if the user writes a long commit message and your pre-commit hook tells them the message is bad, they won't have their message entirely thrown away.
