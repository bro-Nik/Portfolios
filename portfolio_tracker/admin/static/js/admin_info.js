// Info
function UpdateInfo(url) {

  $.get(url).done(function(data) {

    // Информация
    var $box = $(`.info-box`).empty();
    $.each(data.info, function(index, data){       

      var $item = $('<div>', {});
      if (data.group_name) {
        // Заголовок группы
        $item.append(`<span class="me-3 text-average">${data.group_name}</span>`)
      } else {
        // Список информации
        $item.append(`<span class="me-3">${data.name}</span><span class="text-average">${data.value}</span>`)
      }
      $box.append($item);
    })
    // Заглушка, если пусто
    if ($box.html() == '') {$box.append($('<span>', {text: 'Нет'}))}

    // События
    var $box = $(`.events-box`).empty();
    $.each(data.events, function(index, data){       
      var box_url = $box.attr('data-url');

      var $item = $('<div>', {});
      if (data.group_name) {
        // Заголовок группы
        $item.append(`<span class="me-3 text-average">${data.group_name}</span>`)
      } else {
        // Список событий
        $item.append(`<span class="me-3">${data.name}</span><span class="text-average">${data.value}</span>`)
        $item.addClass('open-modal')
        $item.attr('data-url', `${box_url}${box_url.includes('?') ? '&' : '?'}event=${data.key}`)
      }
      $box.append($item);
    })
    // Заглушка, если пусто
    if ($box.html() == '') {$box.append($('<span>', {text: 'Нет'}))}

    // Потоки
    var $box = $(`.streams-box`).empty();
    $.each(data.streams, function(index, data){       

      var $item = $('<div>', {});
      $item.append(`<span class="me-3">${data.name}:</span>
                    <span class="me-3">${data.calls}</span>
                    <span class="me-3">${data.api_key}</span>
                    <span class="me-3">${data.called}</span>
                    <span class="text-average">${data.status}</span>`
      )
      $box.append($item);
    })
    // Спрятать, если пусто
    if ($box.html() == '') {$box.parent().addClass('visually-hidden')}
    else {$box.parent().removeClass('visually-hidden')}
  })
}

UpdateInfo($('.info-url').data('url'));
clearTimeout(UpdateInfoTimerId);
var UpdateInfoTimerId = setInterval(UpdateInfo, 10000, $('.info-url').data('url'));
