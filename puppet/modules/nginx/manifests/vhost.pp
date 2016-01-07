define nginx::vhost ($ensure = present, $content = undef) {

  File {
    require => Package[nginx],
    notify  => Service[nginx],
  }

  validate_re($ensure, '^(present|absent)$',
    "${ensure} is not supported for ensure. Allowed values are 'present' and 'absent'.")

  $conf_root = "/etc/nginx"
  $conf_available = "${conf_root}/sites-available/${name}.conf"
  $conf_enabled = "${conf_root}/sites-enabled/${name}.conf"

  if $ensure == "present" {

    file {
      $conf_available:
        ensure  => present,
        content => $content;
      $conf_enabled:
        ensure  => $conf_available;
    }

  } else {

    file {
      $conf_available:
        ensure  => absent;
      $conf_enabled:
        ensure  => absent;
    }

  }

}
