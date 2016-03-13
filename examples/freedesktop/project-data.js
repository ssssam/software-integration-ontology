"use strict";

// Order the projects according to the "follows" property.
function projects_ordered(projects) {
    var projects_index = Object();

    function find_project(name) {
        if (! (name in projects_index)) {
            for (var i=0, length=projects.length; i < length; i++) {
                if (projects[i].name == name) {
                    projects_index[name] = project;
                    break;
                }
            }
        }

        if (projects_index[name] === undefined)
            throw new Error("Reference to unknown project " + name);

        return projects_index[name];
    }

    var order = [];
    for (var i=0, length=projects.length; i < length; i++) {
        var project = projects[i];

        if (project.follows === undefined) {
            order.unshift(project);
            project.index = 0;
        } else {
            var follows = find_project(project.follows);
            if (follows.index === undefined) {
                order.push(project);
                project.index = order.length;
            } else {
                order.splice(follows.index, 0, project);
                project.index = follows.index + 1;
            }
        }
    }

    console.log("order:", order);
    return order;
}
