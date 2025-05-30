# Installing Git and Cloning the Repository

The utilities in this project require Git so you can obtain the source code. The instructions below cover installing Git on Windows (using WSL) and on macOS, then cloning the repository.

## On Windows using WSL

1. Launch your **Ubuntu** (or other Linux) distribution from the Windows Terminal.
2. Update package lists and install Git:
   ```bash
   sudo apt update && sudo apt install git
   ```
3. Configure your name and email for commits:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
4. Clone the repository:
   ```bash
   git clone https://github.com/dhisana-ai/gtm-ai-tools.git
   cd gtm-ai-tools
   ```

## On Macbook

1. Open **Terminal**.
2. If you use **Homebrew**, install Git with:
   ```bash
   brew install git
   ```
   Otherwise you can install the Xcode command line tools which include Git:
   ```bash
   xcode-select --install
   ```
3. Clone the repository:
   ```bash
   git clone https://github.com/dhisana-ai/gtm-ai-tools.git
   cd gtm-ai-tools
   ```

Once cloned, you can proceed with building the Docker image and running the utilities.
