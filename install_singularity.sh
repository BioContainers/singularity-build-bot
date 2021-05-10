sudo rm -rf /usr/local/go # remove preinstalled go
sudo apt-get update -qq && sudo apt-get -qq install -y build-essential libssl-dev uuid-dev libgpgme11-dev squashfs-tools libseccomp-dev pkg-config > /dev/null 2>&1
echo "Requirements installed. Installing Go..."

# install go
echo "Downloading Go from https://dl.google.com/go/go1.12.9.linux-amd64.tar.gz and untarring to /usr/local..."
wget -q https://dl.google.com/go/go1.12.9.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.12.9.linux-amd64.tar.gz
rm go1.12.9.linux-amd64.tar.gz
echo "Go successfully installed."

# get deps
echo "Getting Singularity dependencies with go get..."
go get -u github.com/golang/dep/cmd/dep > /dev/null 2>&1
go get -d github.com/sylabs/singularity > /dev/null 2>&1 && exit 0 

# install singularity
echo "Downloading Singularity from https://github.com/sylabs/singularity/archive/refs/tags/v3.3.0.tar.gz and untarring..."
mkdir -p $HOME/go/src/github.com/sylabs
cd $HOME/go/src/github.com/sylabs
wget -q https://github.com/sylabs/singularity/archive/refs/tags/v3.3.0.tar.gz
tar -xzf v3.3.0.tar.gz
cd ./singularity-3.3.0
echo "Running mconfig, make, and make install..."
./mconfig 1> /dev/null
make -C ./builddir 1> /dev/null
sudo make -C ./builddir install 1> /dev/null
echo "Singularity successfully installed."
