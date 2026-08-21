"""Public legal pages (privacy policy) served as standalone HTML.

Kept self-contained (inline CSS, no template dependency) so it can be deployed
by uploading this single file + a urls.py route. The URL
https://colorofit.pythonanywhere.com/privacy/ is referenced in the Google Play
listing, the App Store listing, and inside the app.
"""
from django.http import HttpResponse
from django.views.decorators.http import require_GET

_PRIVACY_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy — CaloriLens</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2rem 1rem 4rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.6; color: #1c1c1e; background: #f7f7f8;
  }
  main { max-width: 720px; margin: 0 auto; background: #fff;
    padding: 2rem 1.6rem; border-radius: 14px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
  h1 { font-size: 1.6rem; margin: 0 0 .25rem; }
  h2 { font-size: 1.15rem; margin: 1.8rem 0 .5rem; }
  .updated { color: #6b7280; font-size: .9rem; margin: 0 0 1.5rem; }
  .meta { background: #f2f4f5; border-radius: 10px; padding: .8rem 1rem; margin: 0 0 1rem; font-size: .95rem; }
  table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; font-size: .92rem; }
  th, td { border: 1px solid #e2e4e8; padding: .5rem .6rem; text-align: left; vertical-align: top; }
  th { background: #f2f4f5; }
  code { background: #f2f4f5; padding: .1rem .3rem; border-radius: 4px; }
  a { color: #2563eb; }
  ul { padding-left: 1.2rem; }
  @media (prefers-color-scheme: dark) {
    body { color: #e5e5e7; background: #0d0d0f; }
    main { background: #17171a; box-shadow: none; }
    .meta, th, code { background: #232327; }
    th, td { border-color: #303036; }
    .updated { color: #9ca3af; }
    a { color: #6ea8fe; }
  }
</style>
</head>
<body>
<main>
  <h1>Privacy Policy — CaloriLens</h1>
  <p class="updated">Last updated: 12 August 2026</p>

  <p>CaloriLens (&ldquo;the app&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;) helps you track meals,
  calories, and water intake and set nutrition goals. This policy explains what data we collect,
  why, and your rights over it.</p>

  <p class="meta"><strong>Data controller:</strong> Sabina Orujova<br>
  <strong>Contact:</strong> <a href="mailto:sabinaorujva@gmail.com">sabinaorujva@gmail.com</a></p>

  <h2>1. Information we collect</h2>
  <p><strong>You provide:</strong></p>
  <ul>
    <li><strong>Account identity</strong> — your email address and basic profile (name, profile photo)
        received from Google Sign-In or Apple Sign-In when you log in.</li>
    <li><strong>Health &amp; fitness data</strong> — weight, height, age, activity level, goal weight,
        goal date, and the calorie/macro targets derived from them.</li>
    <li><strong>Food &amp; water logs</strong> — meals you add (including AI-recognized foods), their
        nutrition values, and your daily water intake.</li>
    <li><strong>Feedback</strong> — any rating or message you submit through the app.</li>
  </ul>
  <p><strong>Collected automatically:</strong></p>
  <ul>
    <li>Device notification token / settings where applicable, to deliver meal and water reminders.</li>
    <li>Basic technical logs needed to operate and secure the service.</li>
  </ul>
  <p>We do <strong>not</strong> knowingly collect data from children under 13.</p>

  <h2>2. How we use your data</h2>
  <ul>
    <li>To calculate and display your calorie/macro targets and progress.</li>
    <li>To store and show your food and water history across your devices.</li>
    <li>To recognize food from photos you choose to scan.</li>
    <li>To send reminders you have enabled.</li>
    <li>To operate, secure, debug, and improve the app.</li>
  </ul>
  <p>We do <strong>not</strong> sell your personal data.</p>

  <h2>3. Third parties we share data with</h2>
  <p>Data is shared only as needed to provide these features:</p>
  <table>
    <thead><tr><th>Provider</th><th>Purpose</th><th>Data shared</th></tr></thead>
    <tbody>
      <tr><td>Google Sign-In / Apple Sign-In</td><td>Authentication</td><td>Identity token, email</td></tr>
      <tr><td>Google Gemini API</td><td>AI food recognition</td><td>The food photo you scan</td></tr>
      <tr><td>Spoonacular API</td><td>Recipe &amp; nutrition lookup</td><td>Your search terms (no account identity)</td></tr>
      <tr><td>PythonAnywhere</td><td>Backend hosting &amp; storage</td><td>All account data listed above</td></tr>
    </tbody>
  </table>
  <p>Each provider processes data under its own terms and privacy policy.</p>

  <h2>4. Sensitive data</h2>
  <p>Health and fitness information is <strong>sensitive personal data</strong> (e.g. GDPR Art. 9).
  We process it only to provide the app&rsquo;s core functionality, on the basis of your consent,
  which you can withdraw at any time by deleting your account.</p>

  <h2>5. Data retention &amp; deletion</h2>
  <ul>
    <li>We keep your data while your account is active.</li>
    <li><strong>You can delete your account and all associated data at any time</strong> from
        <strong>Profile → Delete account</strong>. This is immediate and irreversible.</li>
    <li>On deletion, your food logs, water intake, goals, and profile are permanently removed
        from our database.</li>
  </ul>

  <h2>6. Your rights</h2>
  <p>Depending on your region (e.g. GDPR / similar laws) you may have the right to access, correct,
  export, or delete your data, and to withdraw consent. To exercise these rights, use in-app account
  deletion or contact <a href="mailto:sabinaorujva@gmail.com">sabinaorujva@gmail.com</a>.</p>

  <h2>7. Security</h2>
  <p>We use encrypted connections (HTTPS) and store credentials securely on your device. No method of
  transmission or storage is 100% secure, but we take reasonable measures to protect your data.</p>

  <h2>8. Health disclaimer</h2>
  <p>Calorie and nutrition targets are estimates for general wellness and are <strong>not medical
  advice</strong>. Consult a qualified healthcare professional before making health decisions.</p>

  <h2>9. Changes to this policy</h2>
  <p>We may update this policy; material changes will be reflected by the &ldquo;Last updated&rdquo;
  date above and, where required, notified in-app.</p>

  <h2>10. Contact</h2>
  <p>Questions about this policy or your data:
  <strong><a href="mailto:sabinaorujva@gmail.com">sabinaorujva@gmail.com</a></strong></p>
</main>
</body>
</html>"""


@require_GET
def privacy_policy(request):
    return HttpResponse(_PRIVACY_HTML, content_type="text/html; charset=utf-8")
