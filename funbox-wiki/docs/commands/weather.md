# ⛅️ /weather

Отправляет погоду на сегодня с использованием wttr.in, принимает город в качестве аргумента, пример: <br />

``` telegram
/weather Москва
```

<div className="update-container">

<div className="image-block">
<img
  src={require("/img/weather_no.png").default}
  alt="При отсутствии указанного города"
/>
<p className="image-caption">При отсутствии указанного города</p>
</div>

<div className="image-block">
<img
  src={require("/img/weather_yes.png").default}
  alt="Указан город на русском языке"
/>
<p className="image-caption">Указан город на русском языке</p>
</div>

</div>
