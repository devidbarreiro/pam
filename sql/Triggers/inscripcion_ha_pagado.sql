DELIMITER //

CREATE TRIGGER inscripcion_ha_pagado_before_insert
BEFORE INSERT ON inscripcion
FOR EACH ROW
BEGIN
    IF NEW.a_pagar - NEW.pagado <= 0 THEN
        SET NEW.ha_pagado = 1;
    ELSE
        SET NEW.ha_pagado = 0;
    END IF;
END;
//

CREATE TRIGGER inscripcion_ha_pagado_before_update
BEFORE UPDATE ON inscripcion
FOR EACH ROW
BEGIN
    IF NEW.a_pagar - NEW.pagado <= 0 THEN
        SET NEW.ha_pagado = 1;
    ELSE
        SET NEW.ha_pagado = 0;
    END IF;
END;
//

DELIMITER ;
