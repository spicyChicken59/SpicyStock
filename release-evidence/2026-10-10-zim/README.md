# ZIM known-event correction

Reviewed on 10 October 2026 against the 9 October publication at `62bce72d`.
The anticipation candidate carried a $30.38 trigger, $30.68 limit and $29.66
stop: two shares, $61.36 maximum order cost and $2.04 planned price-to-stop
risk. Its event status was `not_in_registry`; this did not establish news
clearance.

The issuer's 16 February announcement records an agreement for Hapag-Lloyd to
acquire ZIM for $35 per share in cash. Its 30 September SEC report says the
Israeli Government Companies Authority stopped handling the existing approval
application after the detailed revised proposal was not submitted by its
deadline; the same report says Hapag-Lloyd intended to submit a revised
proposal. That report is not a merger termination or a regulatory approval.

The 6 October release raised full-year guidance to adjusted EBITDA of
$2.7–3.0 billion and adjusted EBIT of $1.4–1.7 billion, versus $2.0–2.4 billion
and $0.7–1.1 billion previously. It still describes the Hapag-Lloyd transaction
as pending. The positive business catalyst does not change the existing
strategy's exclusion of unresolved cash acquisitions. No completion date or
future earnings date is established by this review.

`knowledge/event-risk.json` adds the event without changing the exclusion
policy. Its reason uses only the original announcement; later sources are
included only on or after their own dates. The exclusion stays unresolved
after its 16 October review deadline unless a reviewed source establishes a
resolution. This is a bounded manual review, not comprehensive news coverage.

The files below are unchanged HTTP response bytes. [manifest.json](manifest.json)
records their URLs, issuer publication dates, UTC retrieval timestamps, SHA-256
digests and exact excerpts used in the registry:

- [16 February issuer announcement](ir-merger-announcement.html), retrieved
  10 October at 06:04:01 UTC. The issuer page supplies the public announcement
  date; the corresponding SEC Form 6-K was submitted on 17 February.
- [30 September Form 6-K](2026-09-30-6k.html), retrieved 10 October at
  06:02:51 UTC. SEC acceptance timestamp: 30 September at 16:00:11 UTC.
- [6 October guidance release](2026-10-06-release.html), retrieved 10 October
  at 06:03:06 UTC. The enclosing Form 6-K was accepted on 7 October at
  00:10:39 UTC, corresponding to 6 October in New York.

Historical production bytes are preserved. This source correction takes effect
in newly generated publications; adding the evidence alone does not change an
already published ticket.

The issuer announcement also contains a public reCAPTCHA client site key used
by `grecaptcha.render`. [Google's key documentation](https://developers.google.com/recaptcha/intro)
distinguishes this browser identifier from the private server verification key.
The scanner disposition requires both that exact public value and this exact
capture path; the raw HTML and its manifest digest are unchanged. Offline
controls retain detection for other values, copied paths and other credential
types. No detector or complete file is excluded.
