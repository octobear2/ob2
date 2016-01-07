class ob2($home_directory, $owner, $group) {

    File {
        owner => $owner,
        group => $group,
    }

    file {
        "$home_directory/.bashrc":
            ensure => present,
            content => template("ob2/shell/bashrc");
        "$home_directory/.ob2.bashrc":
            ensure => present,
            content => template("ob2/shell/ob2.bashrc");
    }

}
