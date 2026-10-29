"""Browser-side helpers shared by probes and checks.

Each script is a self-contained function expression for ``page.evaluate``; nothing is
installed into the page, so a site's own scripts cannot replace these helpers.
"""

from __future__ import annotations

HELPERS = r"""
const __norm = (value) => (value || '').replace(/\s+/g, ' ').trim();
const __isVisible = (element) => {
  if (!element || !element.isConnected) return false;
  const style = window.getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' &&
    rect.width > 0 && rect.height > 0 && !element.closest('[inert]');
};
const __roleOf = (element) => {
  const explicit = element.getAttribute('role');
  if (explicit) return explicit.split(/\s+/)[0];
  const tag = element.tagName.toLowerCase();
  const type = (element.getAttribute('type') || 'text').toLowerCase();
  if (tag === 'a' && element.hasAttribute('href')) return 'link';
  if (tag === 'button' || tag === 'summary') return 'button';
  if (tag === 'select') return 'combobox';
  if (tag === 'textarea') return 'textbox';
  if (tag === 'input') {
    if (type === 'checkbox') return 'checkbox';
    if (type === 'radio') return 'radio';
    if (type === 'search') return 'searchbox';
    if (type === 'range') return 'slider';
    if (['button', 'submit', 'reset', 'image'].includes(type)) return 'button';
    if (type === 'hidden') return null;
    return 'textbox';
  }
  return null;
};
const __accName = (element) => {
  const byIds = __norm((element.getAttribute('aria-labelledby') || '').split(/\s+/)
    .filter(Boolean).map((id) => document.getElementById(id)?.textContent || '').join(' '));
  if (byIds) return byIds;
  const aria = __norm(element.getAttribute('aria-label'));
  if (aria) return aria;
  const tag = element.tagName.toLowerCase();
  const type = (element.getAttribute('type') || '').toLowerCase();
  const labelText = Array.from(element.labels || []).map((label) => label.textContent);
  const labels = __norm(labelText.join(' '));
  if (labels) return labels;
  if (tag === 'input' && ['button', 'submit', 'reset'].includes(type)) {
    const fallback = type === 'submit' ? 'Submit' : type === 'reset' ? 'Reset' : '';
    return __norm(element.value) || fallback;
  }
  if (tag === 'input' && type === 'image') return __norm(element.getAttribute('alt'));
  if (tag === 'img') return __norm(element.getAttribute('alt'));
  const role = __roleOf(element);
  const fromContent = ['button', 'link', 'checkbox', 'radio', 'menuitem', 'tab', 'option',
    'switch', 'treeitem', 'heading', 'cell', 'gridcell', 'row', 'columnheader'];
  if (!['input', 'select', 'textarea'].includes(tag) && (fromContent.includes(role) || !role)) {
    // Content hidden from assistive technology does not count towards the name.
    const clone = element.cloneNode(true);
    clone.querySelectorAll('[aria-hidden="true"], script, style, template')
      .forEach((node) => node.remove());
    const images = Array.from(clone.querySelectorAll('img[alt]'))
      .map((image) => image.getAttribute('alt')).join(' ');
    const text = __norm((clone.textContent || '') + ' ' + images);
    if (text) return text;
  }
  return __norm(element.getAttribute('title')) || __norm(element.getAttribute('placeholder'));
};
const __cssPath = (element) => {
  const parts = [];
  let node = element;
  while (node && node.nodeType === 1 && parts.length < 8) {
    const tag = node.tagName.toLowerCase();
    if (node.id && /^[A-Za-z][\w-]*$/.test(node.id) &&
        document.querySelectorAll('#' + node.id).length === 1) {
      parts.unshift(tag + '#' + node.id);
      break;
    }
    let part = tag;
    const classes = Array.from(node.classList).filter((name) => /^[A-Za-z_][\w-]*$/.test(name))
      .slice(0, 2);
    if (classes.length) part += '.' + classes.join('.');
    const parent = node.parentElement;
    if (parent) {
      const same = Array.from(parent.children).filter((child) => child.tagName === node.tagName &&
        child.id !== '__accesspath_walk_start');
      if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
    }
    parts.unshift(part);
    if (tag === 'body') break;
    node = parent;
  }
  return parts.join(' > ').slice(0, 512);
};
const __snippet = (element) => {
  const clone = element.cloneNode(false);
  clone.removeAttribute('value');
  if (clone.getAttribute && (clone.getAttribute('type') || '').toLowerCase() === 'password') {
    clone.removeAttribute('autocomplete');
  }
  for (const attribute of Array.from(clone.attributes || [])) {
    if (attribute.name.startsWith('data-accesspath')) {
      clone.removeAttribute(attribute.name);
      continue;
    }
    if (attribute.name === 'style' || attribute.value.length > 120) {
      clone.setAttribute(attribute.name, attribute.value.slice(0, 60) + '…');
    }
  }
  const html = clone.outerHTML || '';
  const closing = `</${element.tagName.toLowerCase()}>`;
  return (html.endsWith(closing) ? html.slice(0, -closing.length) : html).slice(0, 400);
};
const __sourceHint = (element) => {
  const fiberKey = Object.keys(element).find((key) => key.startsWith('__reactFiber$'));
  if (fiberKey) {
    let fiber = element[fiberKey];
    for (let depth = 0; fiber && depth < 12; depth += 1, fiber = fiber.return) {
      const source = fiber._debugSource;
      if (source && source.fileName) {
        return {file: String(source.fileName).slice(-300), line: source.lineNumber || null,
          framework: 'react'};
      }
    }
    return {file: null, line: null, framework: 'react'};
  }
  const vue = element.__vueParentComponent;
  if (vue && vue.type && vue.type.__file) {
    return {file: String(vue.type.__file).slice(-300), line: null, framework: 'vue'};
  }
  return {file: null, line: null, framework: null};
};
const __details = (element) => {
  const rect = element.getBoundingClientRect();
  const hint = __sourceHint(element);
  return {
    tag: element.tagName.toLowerCase(),
    role: __roleOf(element),
    name: __accName(element).slice(0, 200),
    test_id: element.getAttribute('data-testid'),
    dom_id: element.id ? element.id.slice(0, 128) : null,
    classes: Array.from(element.classList).slice(0, 12),
    css_path: __cssPath(element),
    html_snippet: __snippet(element),
    tabindex: element.hasAttribute('tabindex')
      ? element.getAttribute('tabindex').slice(0, 8) : null,
    rect: {x: Math.round(rect.x), y: Math.round(rect.y + window.scrollY),
      width: Math.round(rect.width), height: Math.round(rect.height)},
    source_file: hint.file,
    source_line: hint.line,
    framework: hint.framework,
  };
};
const __isSequentiallyFocusable = (element) => element.tabIndex >= 0 &&
  !element.matches(':disabled') && __isVisible(element);
const __interactiveRoles = ['button', 'link', 'checkbox', 'radio', 'menuitem', 'menuitemcheckbox',
  'menuitemradio', 'tab', 'switch', 'option', 'slider', 'spinbutton', 'combobox', 'textbox',
  'searchbox', 'treeitem'];
"""


def script(body: str, params: str = "") -> str:
    """Wrap a script body with the shared helpers as one function expression."""
    return f"({params}) => {{\n{HELPERS}\n{body}\n}}"


ACTIVE_DETAILS = script(
    """
    const element = document.activeElement;
    if (!element || element === document.body || element === document.documentElement) return null;
    return __details(element);
    """
)
