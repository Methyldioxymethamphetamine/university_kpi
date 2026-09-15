/**
 * NIRF Benchmarking Presentation Application JS
 */

document.addEventListener('DOMContentLoaded', () => {
  initMobileNav();
  initTopbarInstitutionSelector();
  initTableFilters();
});

/**
 * Mobile Drawer Navigation
 */
function initMobileNav() {
  const shell = document.querySelector('.shell');
  const toggleBtn = document.querySelector('.topbar-mobile-toggle');
  const backdrop = document.querySelector('.sidebar-backdrop');

  if (!shell || !toggleBtn) return;

  function toggleNav() {
    const isOpen = shell.classList.toggle('nav-open');
    toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function closeNav() {
    shell.classList.remove('nav-open');
    toggleBtn.setAttribute('aria-expanded', 'false');
  }

  toggleBtn.addEventListener('click', toggleNav);

  if (backdrop) {
    backdrop.addEventListener('click', closeNav);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && shell.classList.contains('nav-open')) {
      closeNav();
    }
  });
}

/**
 * Global Contextual Institution Selector & Filtering
 */
function initTopbarInstitutionSelector() {
  const selects = document.querySelectorAll('.inst-select-control');
  if (!selects.length) return;

  function updateTooltip(sel) {
    const opt = sel.options[sel.selectedIndex];
    if (opt && opt.value) {
      sel.title = opt.getAttribute('title') || opt.textContent.trim();
    } else {
      sel.title = "All Institutions";
    }
  }

  selects.forEach(select => {
    updateTooltip(select);

    select.addEventListener('change', (e) => {
      const target = e.target;
      const val = target.value ? target.value.trim() : '';
      updateTooltip(target);

      // If inside an in-page filter form (e.g. extraction.html), submit the form
      if (target.id === 'filter-inst' && target.form) {
        target.form.submit();
        return;
      }

      // Check current URL and update query parameter
      const url = new URL(window.location.href);

      // Reset page number on filter change
      url.searchParams.delete('page');

      if (val) {
        url.searchParams.set('institution_code', val);
      } else {
        url.searchParams.delete('institution_code');
      }

      // If user is currently on an artifact page and changes institution filter
      if (url.pathname.startsWith('/artifact/')) {
        if (val) {
          window.location.href = `/artifact/${encodeURIComponent(val)}`;
        } else {
          window.location.href = '/';
        }
        return;
      }

      // Standard page navigation with updated query parameter
      window.location.href = url.toString();
    });
  });
}

/**
 * Client-side Table Filter helper
 */
function initTableFilters() {
  const searchInput = document.querySelector('[data-table-search]');
  if (!searchInput) return;

  const tableSelector = searchInput.getAttribute('data-table-search');
  const table = document.querySelector(tableSelector);
  if (!table) return;

  const rows = table.querySelectorAll('tbody tr');

  searchInput.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(term) ? '' : 'none';
    });
  });
}
