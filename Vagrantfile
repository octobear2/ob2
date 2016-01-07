VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # VirtualBox
  config.vm.box = "ubuntu/trusty64"
  config.vm.network "private_network", ip: "192.168.162.42"
  puppet_version = 3

  # Uncomment for VMWare Fusion
  # config.vm.box = "puppetlabs/ubuntu-14.04-64-puppet"
  # config.vm.network "private_network", ip: "192.168.163.42"
  # puppet_version = 4

  config.vm.network "forwarded_port", guest: 5002, host: 5002, host_ip: "127.0.0.1"
  config.vm.hostname = "ob2-dev.eecs.berkeley.edu"

  config.vm.provision "puppet" do |puppet|
    puppet.manifests_path = "puppet/manifests"
    puppet.module_path    = "puppet/modules"
    puppet.manifest_file  = "site.pp"
    if puppet_version == 4
      puppet.environment_path = "puppet/environments"
      puppet.environment = "default"
    end
  end

  config.vm.synced_folder ".", "/home/vagrant/src"

  config.vm.provider "virtualbox" do |v|
    v.memory = 2048
  end

  config.vm.provider "vmware_fusion" do |v|
    v.vmx["memsize"] = 2048
    v.gui = false
  end

end
