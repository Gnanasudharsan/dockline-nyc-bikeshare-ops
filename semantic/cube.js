// Cube configuration. The data model lives in model/cubes/*.yml; this file only
// wires runtime behavior. Connection settings come from CUBEJS_* environment variables.
module.exports = {
  // Pre-aggregations are built by Cube's refresh worker, not on first query.
  scheduledRefreshTimer: 60,
  // The SQL API (Postgres wire protocol on CUBEJS_PG_SQL_PORT) is what Grafana uses.
  // One shared login is enough here: it is read-only and bound to localhost.
  checkSqlAuth: async (_req, user) => {
    if (user !== process.env.CUBEJS_SQL_USER) {
      throw new Error(`Unknown SQL API user: ${user}`);
    }
    return { password: process.env.CUBEJS_SQL_PASSWORD, securityContext: {} };
  },
};
