class ob2::docker {

    file { "/etc/default/docker":
        ensure  => file,
        content => template("ob2/docker/etc.default.docker"),
        notify  => Service[docker];
    }

    service { "docker":
        ensure  => running,
        require => Package["lxc-docker"];
    }

    file { "/etc/apparmor.d/ob2docker":
        ensure  => file,
        content => template("ob2/docker/etc.apparmor.d.ob2docker"),
        notify  => Exec["aa-enable-ob2docker"];
    }

    exec { "aa-enable-ob2docker":
        command     => "apparmor_parser -r -T -W /etc/apparmor.d/ob2docker",
        refreshonly => true,
        user        => root,
        require     => [File["/etc/apparmor.d/ob2docker"], Package["lxc-docker"]];
    }

}
