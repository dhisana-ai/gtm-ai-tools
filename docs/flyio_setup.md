# Quick Testing on Fly.io

This project includes a `fly.toml` file so you can deploy the app to [Fly.io](https://fly.io) without installing Docker locally. Follow the steps below to launch the application in the cloud.

1. **Create an account**
   - Visit <https://fly.io/signup> and sign up using GitHub or email.
   - Install the Fly CLI by running:
     ```bash
     curl -L https://fly.io/install.sh | sh
     ```
     Restart your terminal so `fly` is on your path.

2. **Launch the app**
   - From your cloned `gtm-ai-tools` directory run:
     ```bash
     fly launch
     ```
   - Accept the defaults to create a new application. The command uses the existing `fly.toml` file and provisions a small machine.

3. **Add the required secrets**
   - Set the four mandatory environment variables:
     ```bash
     fly secrets set OPENAI_API_KEY=your_openai_key \
                     SERPER_API_KEY=your_serper_key \
                     DHISANA_API_KEY=your_dhisana_key \
                     APP_PASSWORD=your_password
     ```
   - Additional optional variables from `.env` can also be added with `fly secrets set`.

4. **Deploy**
   ```bash
   fly deploy
   ```
   When the deployment completes, Fly.io prints the application URL.

5. **Open the web interface**
   - Browse to the URL shown in the deploy output.
   - Log in with the username from `APP_USERNAME` (defaults to `user`) and the password you set in `APP_PASSWORD`.

Use `fly logs` to monitor output or troubleshoot any issues. When you are finished testing you can remove the app with `fly apps destroy <app-name>`.
