import { createApp, lakebase, server } from '@databricks/appkit';
import { setupNipRoutes } from './routes/nip-routes';

createApp({
  plugins: [lakebase(), server()],
  async onPluginsReady(appkit) {
    await setupNipRoutes(appkit);
  },
}).catch(console.error);
