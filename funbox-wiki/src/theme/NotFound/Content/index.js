import React from 'react';
import clsx from 'clsx';
import Translate from '@docusaurus/Translate';
import Heading from '@theme/Heading';
export default function NotFoundContent({className}) {
  return (
    <main className={clsx('container margin-vert--xl', className)}>
      <div className="row">
        <div className="col col--6 col--offset-3">
          <div style={{ textAlign: 'center', padding: '5rem' }}>
            <h1>Ошибка 404</h1>
            <p>Извините, страница не найдена.</p>
            <a href="/Komaru-FunBox">Вернуться на главную</a>
          </div>
        </div>
      </div>
    </main>
  );
}
