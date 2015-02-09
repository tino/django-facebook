from setuptools import setup, find_packages

setup(
    name='django-facebook2',
    version='0.2',
    description='Facebook Authentication for Django',
    long_description=open('README.md').read(),
    author='Tino de Bruijn',
    author_email='tinodb@gmail.com',
    url='http://github.com/tino/django-facebook2',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'django>=1.5',
        'facebook2>=2.2',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
