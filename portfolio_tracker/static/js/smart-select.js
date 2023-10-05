$(function () {
  $("body").mousedown(function (e) {
    var $select = $('body .smart-select.on');
    if ($select.length && !$(e.target).closest('.smart-select-box').is($select.closest('.smart-select-box'))) {
      $select.trigger('click');
    }
  });
})

function UpdateSmartSelects($element = $("body")) {
  $element.find('select').each(function() {
    if ($(this).hasClass('visually-hidden')) {
      return false;
    }

    if ($(this).attr('disabled')) {
      return false;
    }

    var $select = $(this),
      selectedOption = $select.find('option:selected'),
      selectClass = $(this).attr('class');

    $select.addClass('visually-hidden');
    $select.wrap('<div class="smart-select-box"></div>');
    $('<div>', {
        class: 'smart-select' + (selectClass ? ' ' + selectClass : ''),
        text: selectedOption.length ? selectedOption.text() : $select.attr('data-placeholder') || ' '
    }).insertAfter($select);


    var selectHead = $select.next('.smart-select');
    $('<div>', {
        class: 'smart-select__list'
    }).insertAfter(selectHead);

    var selectList = selectHead.next('.smart-select__list');
    // selectList.slideUp(0);

    $select.on('focus', function() {
      $(this).trigger('blur');
      selectHead.trigger('click');
    })

    selectHead.on('click', function() {
      if (!$(this).hasClass('on')) {
        $(this).addClass('on');
        if (selectHead.offset().top > $(window).height() / 4) {
          selectList.css('bottom', '45px');
        }
        
        // load options
        if ($select.attr('data-url')) {
          GetOptions($select);
        } else {
          GenerateSelect($select)
        }
      } else {
        $(this).removeClass('on');
        // selectList.slideUp(50);
        selectList.fadeOut(50);
      }
    });

  });
}

function GenerateSelect($select) {
  var options_list = $select.parent().find('.smart-select__item').length,
    selectList = $select.next('.smart-select').next('.smart-select__list');

  if (!options_list) {
    var selectOption = $select.find('option'),
      selectOptionLength = selectOption.length;

    for (let i = 0; i < selectOptionLength; i++) {
      if (selectOption.eq(i).val() && selectOption.eq(i).text()) {
        var is_selected = selectOption.eq(i).prop('selected') ? ' selected' : '';

        var text = '<span class="text">' + selectOption.eq(i).text() + '</span>';
        if (selectOption.eq(i).data('subtext')) {
          text += '<span class="subtext">' + selectOption.eq(i).data('subtext') + '</span>';
        }
        $('<div>', {
          class: 'smart-select__item' + is_selected,
          html: text 
        })
        .attr('data-value', selectOption.eq(i).val())
        .appendTo(selectList);
      }
    }
  }
  ClickInSelect($select);
  // selectList.slideDown(50);
  // selectList.slideToggle(100);
  selectList.fadeIn(50);
}

function GetOptions($select) {
  var selectedOptionValue = $select.find('option:selected').val();
  $.get($select.attr('data-url'), function (data) {
    data = $.parseJSON(data);

    $select.empty().append($('<option>', {value: '', text: ''}));

    for (let i = 0; i < data.length; i++) {
      var $newOption = $('<option>', {
        value: data[i].value,
        text: data[i].text
      }).data('subtext', data[i].subtext)

      $select.append($newOption);
      if (data[i].value == selectedOptionValue) {
        $newOption.attr('selected', 'selected');
      }
    }
    $select.parent().find('.smart-select__list').empty();
    GenerateSelect($select);
  })
}

function ClickInSelect($select){
  var selectList = $select.next('.smart-select').next('.smart-select__list'),
    selectItem = selectList.find('.smart-select__item'),
    selectHead = $select.next('.smart-select');

  selectItem.on('click', function() {
    var chooseItem = $(this).data('value');

    // selected class
    selectItem.removeClass('selected');
    $(this).addClass('selected');

    $select.val(chooseItem).attr('selected', 'selected').trigger('change');
    selectHead.text($(this).find('.text').text());

    // selectList.slideUp(50);
    selectList.fadeOut(50);
    selectHead.removeClass('on');

    if ($select.data('action-url')) {
      $.get($select.data('action-url') + '?value=' + chooseItem)
      .done(function (data) {
        location. reload();
      });
    }
  });

}

UpdateSmartSelects();
