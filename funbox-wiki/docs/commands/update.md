# 🔄 /update

Обновляет бота, только для персонала, при остутствии обновлений выводит сообщение (см ниже)

<div className="update-container">

<div className="image-block">
<img
  src={require("/img/update_yes.png").default}
  alt="Есть обновления"
/>
<p className="image-caption">При наличии обновлений бот обновляется</p>
</div>

<div className="image-block">
<img
  src={require("/img/update_no.png").default}
  alt="Нет обновлений"
/>
<p className="image-caption">При отсутствии обновлений выводится сообщение</p>
</div>

</div>
