class nginx (
  $conf_dir = "/etc/nginx",
  $ensure = running,
  $enable = true,
){

  package { nginx:
    ensure => installed,
  }

  service { nginx:
    ensure  => $ensure,
    enable  => $enable,
    require => Package[nginx],
  }

  File {
    require => Package[nginx],
    notify  => Service[nginx],
  }

  file {
    $conf_dir:
      ensure  => directory,
      purge   => true,
      recurse => true;
    "${conf_dir}/fastcgi_params":
      content => template("nginx/fastcgi_params");
    "${conf_dir}/mime.types":
      content => template("nginx/mime.types");
    "${conf_dir}/nginx.conf":
      content => template("nginx/nginx.conf");
    "${conf_dir}/proxy_params":
      content => template("nginx/proxy_params");
    "${conf_dir}/scgi_params":
      content => template("nginx/scgi_params");
    "${conf_dir}/uwsgi_params":
      content => template("nginx/uwsgi_params");
    "${conf_dir}/conf.d":
      ensure => directory,
      purge  => true;
    "${conf_dir}/sites-available":
      ensure  => directory,
      purge   => true,
      recurse => true;
    "${conf_dir}/sites-enabled":
      ensure  => directory,
      purge   => true,
      recurse => true;
  }

}
