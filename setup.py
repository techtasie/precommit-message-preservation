import setuptools

setuptools.setup(
	install_requires = ["xdg==4.0.1"],
	extras_require = {
		"develop": [
			"nose2",
		]
	}
)
