import { createApp, genie, lakebase, server } from '@databricks/appkit';
import { setupNipRoutes } from './routes/nip-routes';

createApp({
  // genie() reads DATABRICKS_GENIE_SPACE_ID and runs each question on behalf of the
  // signed-in user, so Unity Catalog masking applies to the agent's answers too.
  plugins: [lakebase(), genie(), server()],
  async onPluginsReady(appkit) {
    await setupNipRoutes(appkit);
  },
}).catch(console.error);
