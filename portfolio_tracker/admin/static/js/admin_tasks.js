var $tasks_box = $('body').find('.tasks-box').attr('style', 'width: max-content;');
var $logs_box = $('.logs-box');

// Tasks
function UpdateTasks() {
  var url = $tasks_box.data('url'),
    url_action = $tasks_box.data('url-action'),
    url_settings = $tasks_box.data('url-settings'),
    request = $.get(url);
  url_action += `${url_action.includes('?') ? '&' : '?'}action=`

  // Placeholder
  $tasks_box.html(`<div class="spinner-border spinner-border-sm text-secondary"></div>`);

  request.done(function(tasks) {
    $tasks_box.empty();

    var a = '<a class="text-decoration-none" href="#"></a>';
    for (let i = 0; i < tasks.length; i++) {

      var $task = $(`<div class="d-flex"></div>`);
      $task.append($(`<span class="open-modal" >${tasks[i].name_ru}</span>`)
      .attr('data-url', `${url_settings}${url_settings.includes('?') ? '&' : '?'}task_name=${tasks[i].name}`)
      .attr('data-modal-id', 'TaskSettingsModal'));

      var $link = $(a).addClass('ms-3');

      if (tasks[i].id) {
        $link.data('url', `${url_action}stop&task_id=${tasks[i].id}`).text('Остановить').addClass('text-red');
      } else {
        $link.data('url', `${url_action}start&task_name=${tasks[i].name}`).text('Запустить');
      }

      $task.append($(`<span class="ms-auto"></span>`).append($link))
      $tasks_box.append($task)
    }

    if ($tasks_box.html() == '') {
      // Заглушка, если пусто
      $tasks_box.append($('<span>', {text: 'Нет'}))
    } else {
      // Кнопки для всех задач
      $tasks_box.append($(`<div class="mt-3"></div>`).append($(a)
        .data('url', `${url_action}start`).text('Запустить все повторяющиеся')))
      // $tasks_box.append($(`<div class="mt-3"></div>`).append($(a)
      //   .data('url', `${url_action}start`).text('Запустить все')))
      $tasks_box.append($(`<div></div>`).append($(a)
        .data('url', `${url_action}stop`).text('Остановить все').addClass('text-red')))
    }

    // Запуск и остановка задач
    $tasks_box.on("click", "a", function (event) {
      event.preventDefault();
      var url = $(this).data('url');
      $tasks_box.html(`<div class="spinner-border spinner-border-sm text-secondary"></div>`);
      $.get(url).done(function () {
        setTimeout(UpdateTasks, 2000);
      })
    })
  })
}

// Logs
function UpdateLogs(url) {
  var timestamp = $logs_box.find('.log-item').data('timestamp') || 0,
    url = `${url}${url.includes('?') ? '&' : '?'}timestamp=${timestamp}`,
    request = $.get(url);

  request.done(function(logs) {
    for (let i = 0; i < logs.length; i++) {
      var datetime = new Date(logs[i].time).toLocaleString("ru");
      $logs_box.prepend($('<div>', {
        class: 'd-flex flex-wrap log-item',
        html: `<span>${logs[i].text}</span><span class="ms-auto">${datetime}</span>`
      }).data('timestamp', logs[i].timestamp)
      .data('category', logs[i].category))

      // Количество по типу
      var log_category_count = $(`.log-category-${logs[i].category}-count`)
      log_category_count.text(+log_category_count.text() + 1)
    }
    $('.log-category input:checked').trigger('change');
  })
}

$(function () {

  // Filter by category
  $("body").on("change", ".log-category", function () {
    filter_by = +$(this).find('input:checked').val();

    $.each($logs_box.find('.log-item'), function(){       
      if (+$(this).data('category') >= filter_by) {
        $(this).removeClass('visually-hidden')
      } else {
        $(this).addClass('visually-hidden')
      }
    });
  });
})

if ($tasks_box.length){
  UpdateTasks();
}

if ($logs_box.length){
  UpdateLogs($logs_box.data('url'));
  clearTimeout(UpdateLogsTimerId);
  var UpdateLogsTimerId = setInterval(UpdateLogs, 10000, $logs_box.data('url'));
}
