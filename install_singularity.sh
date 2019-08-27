sudo rm -rf /usr/local/go # remove preinstalled go
sudo apt-get update && sudo apt-get install -y build-essential libssl-dev uuid-dev libgpgme11-dev squashfs-tools libseccomp-dev pkg-config

# install go
wget https://dl.google.com/go/go1.12.9.linux-amd64.tar.gz
sudo tar -C /usr/local -xzvf go1.12.9.linux-amd64.tar.gz
rm go1.12.9.linux-amd64.tar.gz

# get deps
go get -u github.com/golang/dep/cmd/dep
go get -d github.com/sylabs/singularity && exit 0

# install singularity
mkdir -p $HOME/go/src/github.com/sylabs
cd $HOME/go/src/github.com/sylabs
wget https://github.com/sylabs/singularity/releases/download/v3.3.0/singularity-3.3.0.tar.gz
tar -xzf singularity-3.3.0.tar.gz
cd ./singularity
./mconfig
make -C ./builddir
sudo make -C ./builddir install