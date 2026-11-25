/* Applies window.SITE branding to header, footer, title, and icon. */
(function () {
  const site = window.SITE;
  if (!site) return;
  const base = document.documentElement.getAttribute('data-base') || '';
  const badge = base + site.badge;
  const home = base + site.home;
  const icon = document.querySelector('link[rel="icon"]');
  if (icon) icon.href = badge;
  document.querySelectorAll('[data-site-name]').forEach((el) => { el.textContent = site.name; });
  document.querySelectorAll('[data-site-disclaimer]').forEach((el) => { el.textContent = site.disclaimer; });
  document.querySelectorAll('img[data-site-badge]').forEach((el) => {
    el.src = badge;
    el.alt = site.name + ' badge';
  });
  const brandLabel = document.querySelector('[data-site-brand-label]');
  if (brandLabel) brandLabel.innerHTML = site.nameHtml;
  if (document.body && document.body.dataset.applyTitle !== 'false') {
    const page = document.body.dataset.pageTitle;
    if (page) document.title = page + ' | ' + site.name;
    else if (!document.title || document.title.indexOf('Pennsylvania') >= 0 || document.title.indexOf('Young Republicans') >= 0) {
      document.title = site.name;
    }
  }
})();
