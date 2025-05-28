var notify_badge_class;
var notify_menu_class;
var notify_api_url;
var notify_fetch_count;
var notify_unread_url;
var notify_mark_all_unread_url;
var notify_refresh_period = 150000000;
var consecutive_misfires = 0;
var registered_functions = [];

// Remplit l'élément badge avec le nombre de notifications non lues
function fill_notification_badge(data) {
    var badges = document.getElementsByClassName(notify_badge_class);
    if (badges) {
        for (var i = 0; i < badges.length; i++) {
            badges[i].innerHTML = data.unread_count;
        }
    }
}

// Remplit la liste des notifications dans le menu
function fill_notification_list(data) {
    var menus = document.getElementsByClassName(notify_menu_class);
    if (menus) {
        var messages = data.unread_list.map(function(item) {
            var message = "";
            if (typeof item.actor !== 'undefined') {
                message = item.actor;
            }
            if (typeof item.verb !== 'undefined') {
                message += " " + item.verb;
            }
            if (typeof item.target !== 'undefined') {
                message += " " + item.target;
            }
            if (typeof item.timestamp !== 'undefined') {
                message += " " + item.timestamp;
            }
            return '<li>' + message + '</li>';
        }).join('');

        for (var i = 0; i < menus.length; i++) {
            menus[i].innerHTML = messages;
        }
    }
}

// Enregistre les fonctions de rappel pour les notifications
function register_notifier(func) {
    registered_functions.push(func);
}

// Fonction de récupération des données de l'API (désactivée)
function fetch_api_data() {
    if (registered_functions.length > 0) {
        var r = new XMLHttpRequest();
        r.addEventListener('readystatechange', function(event) {
            if (this.readyState === 4) {
                if (this.status === 200) {
                    consecutive_misfires = 0;
                    var data = JSON.parse(r.responseText);
                    for (var i = 0; i < registered_functions.length; i++) {
                        registered_functions[i](data);
                    }
                } else {
                    consecutive_misfires++;
                }
            }
        });

        // Désactivation de l'envoi de requêtes
        // r.open("GET", notify_api_url + '?max=' + notify_fetch_count, true);
        // r.send();
    }

    // Désactivation de la répétition automatique des requêtes
    // if (consecutive_misfires < 10) {
    //     setTimeout(fetch_api_data, notify_refresh_period);
    // } else {
    //     var badges = document.getElementsByClassName(notify_badge_class);
    //     if (badges) {
    //         for (var i = 0; i < badges.length; i++) {
    //             badges[i].innerHTML = "!";
    //             badges[i].title = "Connection lost!";
    //         }
    //     }
    // }
}

// Désactivation de l'initialisation du premier appel de fetch_api_data
// setTimeout(fetch_api_data, 1000);
