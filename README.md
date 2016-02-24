# ob2: An autograder and grade database for GitHub-based courses

Octobear 2 (ob2) is a framework for grading programming assignments, used at UC Berkeley. It comes with a dashboard for students, an administration interface for TA's, tools for running autograder scripts inside Docker, a transactional grade database with an audit log, a transactional email daemon, and a set of integrations with GitHub. It takes care of all the infrastructural details, so you can focus on writing great autograders.

## Philosophy

Computer Science courses will always be TA'ed by talented computer programmers. Don't add any functionality that could be accomplished with a Google Form, SQL, or some Python scripting.

## Quick-start guide

Here is the quickest way of getting started with ob2.

1. Download Vagrant and VirtualBox
1. Download a copy of ob2 and run `vagrant up` inside the project root
1. Use `vagrant ssh` to log in to the virtual machine
1. Run `sudo apt-get install linux-image-extra-$(uname -r)` and then **reboot the VM** with `vagrant reload`. If apt-get reported that the kernel extras package is already installed, you don't need to reboot.
1. Create a new Python virtual environment with `virtualenv ./env`
1. Activate the new virtual environment with `source ./env/bin/activate`
1. The ob2 code is mounted inside the virtual machine at `~/src`, so enter the directory with `cd src/`
1. Install the necessary Python packages with `pip install -r requirements.txt`
1. The APSW python package is not available via PyPI, so build it manually by running `./build_apsw.sh`
1. You can now start the ob2 server with `python -m ob2`
1. When ob2 starts, it will try to initialize the database, so press 'y' and hit Enter to continue
1. The `Vagrantfile` bundled with ob2 should have forwarded port 5002 (the default web port) for you, so go to [localhost:5002](http://localhost:5002/) to access the ob2 web interface.

At this point, you should have a working instance of ob2, but it will not be very useful. You won't be able to log in without GitHub OAuth tokens, and there won't be any jobs configured.

See the article on [Configuring ob2](https://github.com/octobear2/ob2/wiki/Configuring-ob2) to get started on setting up your own ob2 configuration.

If you want to use VMware Fusion instead of VirtualBox, see [VMware Fusion support](https://github.com/octobear2/ob2/wiki/Setting-up-ob2-%28the-easy-way%29#vmware-fusion-support).

For more details about setting up ob2 in production environments, see [Setting up ob2 (the hard way)](https://github.com/octobear2/ob2/wiki/Setting-up-ob2-%28the-hard-way%29).

## Contributing

For Python code, use PEP8 standards, but with 100-character line width.

For HTML, use 100-character line width and your own discretion.

For plaintext email templates, try to keep lines to 75 characters.

## License

BSD 2-clause license (see LICENSE.txt)
