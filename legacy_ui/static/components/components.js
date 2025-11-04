(function () {
  const toastContainerId = 'toast-container';

  window.Toast = {
    show({ title, message, intent = 'info', duration = 4000 } = {}) {
      let container = document.getElementById(toastContainerId);
      if (!container) {
        container = document.createElement('div');
        container.id = toastContainerId;
        container.className = 'toast-container';
        document.body.appendChild(container);
      }

      const toast = document.createElement('div');
      toast.className = `toast toast--${intent}`;
      toast.role = intent === 'danger' ? 'alert' : 'status';

      toast.innerHTML = `
        <div class="toast__body">
          ${title ? `<strong class="toast__title">${title}</strong>` : ''}
          ${message ? `<p class="toast__message">${message}</p>` : ''}
        </div>
        <button class="toast__close" type="button" aria-label="Cerrar notificación">×</button>
      `;

      const close = () => {
        toast.classList.add('toast--leaving');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
      };

      toast.querySelector('.toast__close').addEventListener('click', close);
      container.appendChild(toast);

      if (duration > 0) {
        setTimeout(close, duration);
      }

      return close;
    },
  };

  if (!window.mcpHeader) {
    window.mcpHeader = {
      showNotification(message, type = 'info') {
        const intentMap = { success: 'success', warning: 'warning', error: 'danger', info: 'info' };
        window.Toast.show({ message, intent: intentMap[type] || 'info' });
      },
    };
  }

  const initTabs = (root = document) => {
    root.querySelectorAll('[data-component="tabs"]').forEach((tabs) => {
      if (tabs.dataset.tabsInitialized === 'true') return;
      tabs.dataset.tabsInitialized = 'true';
      tabs.addEventListener('click', (event) => {
        const target = event.target;
        if (!target.classList.contains('tab')) return;
        tabs.querySelectorAll('.tab').forEach((tab) => {
          tab.classList.toggle('tab--active', tab === target);
        });
        tabs.dispatchEvent(new CustomEvent('tab-change', {
          detail: { value: target.dataset.tab },
        }));
      });
    });
  };

  const initSegmented = (root = document) => {
    root.querySelectorAll('[data-component="segmented"]').forEach((group) => {
      if (group.dataset.segmentedInitialized === 'true') return;
      group.dataset.segmentedInitialized = 'true';
      group.addEventListener('click', (event) => {
        const target = event.target;
        if (!target.classList.contains('segment')) return;
        group.querySelectorAll('.segment').forEach((segment) => {
          const isActive = segment === target;
          segment.classList.toggle('segment--active', isActive);
          segment.setAttribute('aria-checked', String(isActive));
        });
        group.dispatchEvent(new CustomEvent('segment-change', {
          detail: { value: target.dataset.value },
        }));
      });
    });
  };

  const loadIncludes = () => {
    const includeNodes = document.querySelectorAll('[data-include]');
    includeNodes.forEach((node) => {
      const src = node.getAttribute('data-include');
      if (!src) return;

      fetch(src)
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Include request failed: ${response.status}`);
          }
          return response.text();
        })
        .then((html) => {
          node.innerHTML = html;
          node.removeAttribute('data-include');
          initTabs(node);
          initSegmented(node);
          if (typeof window.initMcpHeader === 'function') {
            window.initMcpHeader();
          }
        })
        .catch((error) => {
          console.warn('No se pudo cargar el include:', src, error);
        });
    });
  };

  document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSegmented();
    loadIncludes();
  });
})();
