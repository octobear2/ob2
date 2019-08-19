node default {

  Exec {
    path => [
      '/usr/local/sbin',
      '/usr/local/bin',
      '/usr/sbin',
      '/usr/bin',
      '/sbin',
      '/bin'
    ]
  }

  $home = "/home/vagrant"
  $user = "vagrant"
  $group = "vagrant"

  user { $user:
    groups  => ["docker"],
    require => Package[docker-ce];
  }

  # Configure apt

  class { "apt":
    update => {
      frequency => always,
    },
  }

  apt::source { "docker":
    location => "https://download.docker.com/linux/ubuntu",
    release  => bionic,
    repos    => stable,
    before   => Package[docker-ce],
    key      => {
      id     => "9DC858229FC7DD38854AE2D88D81803C0EBFCD88",
      source => "https://download.docker.com/linux/ubuntu/gpg",
    },
  }

  include apt::update

  Exec['apt_update'] -> Package <| |>

  # Install some required packages

  package {
    [
      "docker-ce",
      "python-pip",
      "git",
      "python-dev",
      "unzip",
      "libffi-dev",
      "libssl-dev",
      "vim",
      "sqlite3",
    ]:
      ensure => installed;
    "virtualenv":
      ensure   => installed,
      provider => pip,
      require  => Package[python-pip];
  }

  class { "ob2":
    home_directory => $home,
    owner          => $user,
    group          => $group,
  }

  include ob2::docker

}
