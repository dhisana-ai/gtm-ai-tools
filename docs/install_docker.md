# Installing Docker

## On Windows using WSL

1. Open **PowerShell** as Administrator and run `wsl --install` to enable WSL&nbsp;2.
2. Install the **Ubuntu** distribution from the Microsoft Store and launch it once to finish setup.
3. Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
4. In Docker Desktop settings enable **WSL integration** for your Ubuntu distribution.
5. Open your Ubuntu terminal and verify the installation with:
   ```bash
   docker --version
   ```

## On Macbook

1. Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/). Choose the Intel or Apple chip version that matches your hardware.
2. Open the downloaded `.dmg` file and drag **Docker** to **Applications**.
3. Launch Docker from **Applications** and grant the requested privileges.
4. Verify the installation from **Terminal**:
   ```bash
   docker --version
   ```
