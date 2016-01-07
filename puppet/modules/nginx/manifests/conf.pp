define nginx::conf ($ensure = present, $content = undef) {

  nginx::include { "conf.d/${title}":
    name    => "conf.d/${name}",
    ensure  => $ensure,
    content => $content,
  }

}
