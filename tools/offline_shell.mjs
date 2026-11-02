/* The committed page shell names the deployed morning receipt endpoint (the
   `spicystock-morning-endpoint` meta tag in docs/index.html). An offline check
   reads a copy of the shell with that endpoint blanked, so no check depends on
   the live service or reads it in place of its fixtures; the one suite that
   tests the endpoint (morning_service_reader_cases.mjs) sets its own. */
const TAG = /(<meta name="spicystock-morning-endpoint" content=")[^"]*(")/;

const attribute = value => String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;');

/** The shell with its morning endpoint set to `endpoint` ('' disables it). */
export function withEndpoint(html, endpoint) {
  if (!TAG.test(html)) throw Error('the page shell carries no morning endpoint tag');
  return html.replace(TAG, (_, open, close) => open + attribute(endpoint) + close);
}

/** The shell an offline check serves: its morning endpoint blanked, when it has one
    (a shell from before the tag existed is served as it is). */
export function offline(html) {
  return TAG.test(html) ? withEndpoint(html, '') : html;
}
