sudo rm -rf /usr/local/go # remove preinstalled go
sudo apt-get update -qq && sudo apt-get -qq install -y build-essential libssl-dev uuid-dev libgpgme11-dev squashfs-tools libseccomp-dev pkg-config > /dev/null 2>&1
echo "Requirements installed. Installing Go..."

# install go
echo "Downloading Go from https://dl.google.com/go/go1.12.9.linux-amd64.tar.gz and untarring to /usr/local..."
wget -q https://dl.google.com/go/go1.12.9.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.12.9.linux-amd64.tar.gz
rm go1.12.9.linux-amd64.tar.gz
#echo 'export GOPATH=${HOME}/go' >> ~/.bashrc
#echo 'export PATH=/usr/local/go/bin:${PATH}:${GOPATH}/bin' >> ~/.bashrc
export GOPATH=${HOME}/go
export PATH=/usr/local/go/bin:${PATH}:${GOPATH}/bin
source ~/.bashrc
echo "Go successfully installed."

# get deps
#echo "Getting Singularity dependencies with go get..."
#go get -u github.com/golang/dep/cmd/dep > /dev/null 2>&1
#go get -d github.com/sylabs/singularity > /dev/null 2>&1 && exit 0 

# install singularity
echo "Downloading Singularity from https://github.com/sylabs/singularity..."
mkdir -p ${GOPATH}/src/github.com/sylabs
cd ${GOPATH}/src/github.com/sylabs
git clone https://github.com/sylabs/singularity.git
cd singularity
git checkout v3.3.0
./mconfig
cd ./builddir
make
sudo make install
