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
    require => Package[lxc-docker];
  }

  # Configure apt

  class { "apt":
    update => {
      frequency => always,
    },
  }

  apt::source { "docker":
    location => "https://get.docker.io/ubuntu",
    release  => docker,
    repos    => main,
    before   => Package[lxc-docker],
    key      => {
      id     => "36A1D7869245C8950F966E92D8576A8BA88D21E9",
      server => "keyserver.ubuntu.com",
    },
  }

  include apt::update

  Exec['apt_update'] -> Package <| |>

  # Install some required packages

  package {
    [
      "lxc-docker",
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
