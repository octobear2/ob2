define nginx::include ($ensure = present, $content = undef) {

  File {
    require => Package[nginx],
    notify  => Service[nginx],
  }

  validate_re($ensure, '^(present|absent)$',
    "${ensure} is not supported for ensure. Allowed values are 'present' and 'absent'.")

  $conf_file = "/etc/nginx/${name}.conf"

  if $ensure == "present" {

    file { $conf_file:
      ensure => present,
      content => $content,
    }

  } else {

    file { $conf_file:
      ensure => absent,
    }

  }

}
