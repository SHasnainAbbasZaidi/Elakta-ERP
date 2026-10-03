document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !/\/(delete|approve)\//.test(url.pathname)) return;
    event.preventDefault();
    if (!link.hasAttribute('onclick') && !confirm('Confirm this action?')) return;
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!token) return;
    const form = document.createElement('form');
    form.method = 'post';
    form.action = url.pathname;
    form.appendChild(token.cloneNode());
    document.body.appendChild(form);
    form.submit();
  });
  document.querySelectorAll('table.table').forEach(table => {
    if (!table.closest('.table-responsive')) {
      const wrapper = document.createElement('div');
      wrapper.className = 'table-responsive';
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    }
  });
  document.querySelectorAll('.card[onclick]').forEach(card => {
    card.tabIndex = 0;
    card.setAttribute('role', 'link');
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter') card.click();
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.getElementById('sidebar').classList.contains('show')) toggleMobileSidebar();
  });
});

document.addEventListener('DOMContentLoaded', () => {
 document.querySelectorAll('[data-date-preset]').forEach(select => {
  const update = () => { const custom = select.value === 'custom'; select.form.querySelectorAll('[data-date-fields]').forEach(fields => { fields.hidden = !custom; fields.classList.toggle('d-none', !custom); fields.querySelectorAll('input').forEach(input => input.disabled = !custom); }); };
  update(); select.addEventListener('change', () => { update(); if(select.value !== 'custom') select.form.requestSubmit(); });
 });
});
