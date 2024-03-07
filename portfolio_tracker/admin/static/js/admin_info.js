// Info
function UpdateInfo(url) {
  dropdown_box = (`
    <td class="align-middle text-end">
	    <div class="dropdown dropstart">
	      <a href="#" class="link-secondary" role="button" id="dropdownAction" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
	        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="ms-2" viewBox="0 0 16 16"><path d="M9.5 13a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm0-5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm0-5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z"/></svg>
        </a>
        <div class="dropdown-menu" aria-labelledby="dropdownAction"></div>
      </div>
    </td>
  `)

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
    var group_name = '';
    $.each(data.events, function(index, data){       
      var box_url = $box.attr('data-url');

      var $item = $('<div>', {});
      if (data.group_name) {
        // Заголовок группы
        $item.append(`<span class="me-3 text-average">${data.group_name}</span>`)
        group_name = data.group_name;
      } else {
        // Список событий
        $item.append(`<span class="me-3">${data.name}</span><span class="text-average">${data.value}</span>`)
        $item.addClass('open-modal')
        $item.attr('data-modal-id', 'EventModal')
        $item.attr('data-url', `${box_url}${group_name.toLowerCase()}${box_url.includes('?') ? '&' : '?'}event=${data.key}`)
      }
      $box.append($item);
    })
    // Заглушка, если пусто
    if ($box.html() == '') {$box.append($('<span>', {text: 'Нет'}))}

    // Потоки
    var $box = $(`.streams-box`);

    $.each(data.streams, function(index, data){       

      // Поиск или создание tr
      var $tr = $box.find(`#stream_id_${data.id}`);
      if ($tr.length) {
        // Старая строка
        $tr.find('.stream-calls').text(data.calls);
        $tr.find('.stream-called').text(data.called);
        $tr.find('.stream-status').text(data.status);
      } else {
        // Новая строка
        $tr = $(`<tr id="stream_id_${data.id}"></tr>`);

        $tr.append(`<td>${data.name}</td>
                    <td class="stream-calls">${data.calls}</td>
                    <td>${data.api_key}</td>
                    <td class="stream-called">${data.called}</td>
                    <td class="stream-status text-average">${data.status}</td>`
        )
        // Действия над потоком
        var url_settings = $box.attr('data-url-settings');
        var $dropdown = $(`<td>${dropdown_box}</td>`);
        $dropdown.find('.dropdown-menu').append(`
          <a class="dropdown-item open-modal" data-modal-id="StreamModal"
            data-url="${url_settings}${url_settings.includes('?') ? '&' : '?'}stream_id=${data.id}">Изменить</a>
          <a class="dropdown-item link-danger open-modal-confirmation"
            data-title="Удалить поток?" data-form="#StreamActionForm"
            data-text="Поток будет удален"
            data-action="delete" data-id="${data.id}">Удалить</a>
        `)
        $tr.append($dropdown);
        $box.append($tr);
      }

    })
    // Спрятать, если пусто
    if ($box.html() == '') {$box.parent().addClass('visually-hidden')}
    else {$box.parent().removeClass('visually-hidden')}
  })
}

UpdateInfo($('.info-url').data('url'));
clearTimeout(UpdateInfoTimerId);
var UpdateInfoTimerId = setInterval(UpdateInfo, 10000, $('.info-url').data('url'));
