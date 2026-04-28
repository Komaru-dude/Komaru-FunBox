// @ts-check

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.

 @type {import('@docusaurus/plugin-content-docs').SidebarsConfig}
 */
const sidebars = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: '⚙️ Настройка',
      link: {
        type: 'doc', 
        id: 'setup/setup'
      },
      items: ['setup/faststart', 'setup/selfhost'],
    },
    {
      type: 'category',
      label: '⌨️ Команды',
      link: {
        type: 'doc', 
        id: 'commands/commands'
      },
      items: ['commands/basic', 'commands/ai', 'commands/mods', 'commands/rights', 'commands/settings', 'commands/rp', 'commands/other'],
    },
  ],
};

export default sidebars;
