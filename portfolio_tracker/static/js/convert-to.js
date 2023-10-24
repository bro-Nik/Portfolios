$(function () {

  $('body').on('click', '.convert-text', function () {
    var $box = $(this);

    if ($box.hasClass('active')) {
      return true;
    }

    var old_data = $box.find('.convert-data').text();

    var $form = $('<form>', {
      html: $('<textarea>', {
        class: 'form-control convert-data',
        text: old_data,
        name: $box.data('name')
      })
    }).append(`
      <div class="position-right d-flex gap-1">
        <button class="btn btn-primary btn-sm submit" type="button">` + trans.btn_save + `</button>
        <button class="btn btn-light btn-sm cancel" type="button">` + trans.btn_cancel + `</button>
      </div>
      `);

    $box.addClass('active').empty().append($form);
    $form.find('textarea').focus();

    $form.on('click', '.submit', function () {
      var url = $box.data('url'),
        posting = $.post(url, $form.serialize());

      $form.closest('.modal').data('pre-need-update', true);

      posting.done(function (data) {
        UpdateConvertTo($box, $form.find('.convert-data').val());
      });
    });

    $form.on('click', '.cancel', function () {
      UpdateConvertTo($box, old_data);
    });

  });
})

function CreateConvertTo($element = $("body")) {
  $element.find('.convert-text').each(function () {
    UpdateConvertTo($(this));
  })
}

function UpdateConvertTo($box, data) {
  if (data == undefined) {
    data = $box.find('.convert-data').text();
  }
  $box.removeClass('active').empty().append(`<span class="convert-data">` + data + `</span>`);

  if (!$box.find('.convert-data').text().length) {
    $box.append(`<span>` + $box.data('placeholder') + `</span>`);
  }
}
