
const toast_stack_container_elem = document.getElementById('toast-stack-container');
const error_toast_template_elem = document.querySelector('[data-stack-toast-category="error"]');
const info_toast_template_elem = document.querySelector('[data-stack-toast-category="info"]');
const warning_toast_template_elem = document.querySelector('[data-stack-toast-category="warning"]');

function create_toast_add_to_stack(category, message){
  var new_toast;
  switch(category){
  case 'error':
    new_toast = error_toast_template_elem.cloneNode(true);
    break;
  case 'warning':
    new_toast = warning_toast_template_elem.cloneNode(true);
    break;
  default:
    new_toast = info_toast_template_elem.cloneNode(true);
  }
  var toast_message_elem = new_toast.querySelector('.toast-message');
  if(toast_message_elem){
    toast_message_elem.innerHTML = message;
  }

  toast_stack_container_elem.append(new_toast);
  const toast = bootstrap.Toast.getOrCreateInstance(new_toast);
  toast.show();
  return;
}


function NewToasts(flashed_messages={}){
  if(flashed_messages.hasOwnProperty('messages')){
    var messages = flashed_messages.messages;
    for(var i = 0; i < messages.length; i++){
      var category = messages[i][0];
      var message = messages[i][1];
      create_toast_add_to_stack(category, message);
    }
  }
};
