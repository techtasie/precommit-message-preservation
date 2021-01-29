"Installation instructions."
import setuptools # type: ignore

setuptools.setup(
	install_requires = [],
	extras_require = {
		"develop": [
			"nose2",
			"twine",
			"wheel",
		]
	},
	package_data={
		"precommit_message_preservation": ["py.typed"],
	},
)
